"""Tests for purpose-specific consent management and cryptographic audit logging."""

import pytest
from app import create_app, db
from database.models import User
from security.access_control import enforce_access


# ==============================================================================
# Existing Unit Tests (Preserved)
# ==============================================================================

def test_missing_consent_is_denied():
    assert enforce_access(
        None,
        "research",
        lambda record, purpose: record is not None,
    ) is False


def test_withdrawn_consent_is_denied():
    consent = {"status": "withdrawn"}

    assert enforce_access(
        consent,
        "research",
        lambda record, purpose: record.get("status") == "active",
    ) is False


def test_purpose_mismatch_is_denied():
    consent = {"status": "active", "purpose": "research"}

    assert enforce_access(
        consent,
        "marketing",
        lambda record, purpose: (
            record.get("status") == "active"
            and record.get("purpose") == purpose
        ),
    ) is False


# ==============================================================================
# Integration Tests: Consent Scopes with Audit Trail Recording
# ==============================================================================

@pytest.fixture
def app():
    test_app = create_app({
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "TESTING": True,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-consent-audit-key",
    })

    with test_app.app_context():
        db.create_all()
        u1 = User(id=1, email="compliance_lead@enterprise.com", password_hash="hash1")
        u2 = User(id=2, email="auditor@partner.org", password_hash="hash2")
        db.session.add_all([u1, u2])
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_grant_consent_creates_audit_entry(client):
    """Granting a consent scope creates a CONSENT_GRANTED audit entry with ALLOW decision."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    res = client.post("/api/consent/", json={
        "user_id": "1",
        "purpose": "HR Investigation Summary",
        "data_categories": ["confidential", "profile"],
    })
    assert res.status_code == 201
    data = res.get_json()
    consent_id = data["consent_id"]
    assert consent_id is not None
    assert data["granted"] is True
    assert set(data["data_categories"]) == {"confidential", "profile"}

    # Verify event appears in the user's Audit Trail
    res_audit = client.get("/api/audit")
    assert res_audit.status_code == 200
    events = res_audit.get_json()
    assert len(events) >= 1

    grant_events = [e for e in events if e["event_type"] == "CONSENT_GRANTED"]
    assert len(grant_events) == 1
    event = grant_events[0]

    assert event["decision"] == "ALLOW"
    assert event["original_purpose"] == "HR Investigation Summary"
    assert event["requested_purpose"] == "HR Investigation Summary"
    assert event["sent_to_provider"] is False
    assert consent_id in event["description"]
    assert "confidential" in event["description"]
    assert "profile" in event["description"]
    assert event["user_id"] == 1


def test_withdraw_consent_creates_audit_entry(client):
    """Withdrawing a consent scope creates a CONSENT_WITHDRAWN audit entry with BLOCK decision."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    res = client.post("/api/consent/", json={
        "user_id": "1",
        "purpose": "Customer Support",
        "data_categories": ["email"],
    })
    consent_id = res.get_json()["consent_id"]

    # Withdraw the consent scope
    res_wd = client.post(f"/api/consent/{consent_id}/withdraw")
    assert res_wd.status_code == 200
    wd_data = res_wd.get_json()
    assert wd_data["granted"] is False
    assert wd_data["withdrawn_at"] is not None

    # Verify audit trail has both events
    res_audit = client.get("/api/audit")
    events = res_audit.get_json()

    wd_events = [e for e in events if e["event_type"] == "CONSENT_WITHDRAWN"]
    assert len(wd_events) == 1
    wd_event = wd_events[0]

    assert wd_event["decision"] == "BLOCK"
    assert wd_event["original_purpose"] == "Customer Support"
    assert wd_event["sent_to_provider"] is False
    assert consent_id in wd_event["description"]
    assert "withdrawn" in wd_event["description"].lower()
    assert wd_event["user_id"] == 1


def test_consent_audit_user_isolation(client, app):
    """Audit events appear only for the authenticated user and maintain isolation."""
    # User 1 session
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    client.post("/api/consent/", json={
        "user_id": "1",
        "purpose": "HR Investigation Summary",
        "data_categories": ["confidential"],
    })

    # User 2 session
    client2 = app.test_client()
    with client2.session_transaction() as sess:
        sess["user_id"] = 2

    client2.post("/api/consent/", json={
        "user_id": "2",
        "purpose": "Legal & Compliance Audit",
        "data_categories": ["activity"],
    })

    # Check User 1 audit trail -> sees only User 1 event
    u1_audit = client.get("/api/audit").get_json()
    assert all(e["user_id"] == 1 for e in u1_audit)
    assert any(e["original_purpose"] == "HR Investigation Summary" for e in u1_audit)
    assert not any(e["original_purpose"] == "Legal & Compliance Audit" for e in u1_audit)

    # Check User 2 audit trail -> sees only User 2 event
    u2_audit = client2.get("/api/audit").get_json()
    assert all(e["user_id"] == 2 for e in u2_audit)
    assert any(e["original_purpose"] == "Legal & Compliance Audit" for e in u2_audit)
    assert not any(e["original_purpose"] == "HR Investigation Summary" for e in u2_audit)


def test_consent_audit_hash_chain_integrity(client, app):
    """Cryptographic SHA-256 hash-chain integrity remains valid with consent audit events."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    res1 = client.post("/api/consent/", json={
        "user_id": "1",
        "purpose": "Analytics",
        "data_categories": ["activity"],
    })
    cid1 = res1.get_json()["consent_id"]

    client.post(f"/api/consent/{cid1}/withdraw")

    res2 = client.post("/api/consent/", json={
        "user_id": "1",
        "purpose": "Personalization",
        "data_categories": ["profile"],
    })
    assert res2.status_code == 201

    # Verify hash chain integrity across all events
    res_integ = client.get("/api/audit/integrity")
    assert res_integ.status_code == 200
    integ_data = res_integ.get_json()
    assert integ_data["integrity_valid"] is True
    assert integ_data["entries_checked"] >= 3
