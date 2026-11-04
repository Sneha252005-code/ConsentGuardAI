"""Phase 3 tests: Full chat pipeline, conversation isolation, and AI provider gatekeeper."""

import pytest
from flask import Flask

from app import db
from app.config import Config
from app.routes.genai_routes import genai_bp
from app.routes.record_routes import record_bp
from app.routes.audit_routes import audit_bp
from database.models import User, Conversation, ChatMessage, ProtectedRecord, AuditLog
from database.repositories import (
    create_conversation,
    create_protected_record,
    get_audit_logs,
)
from security.encryption import encrypt_data


@pytest.fixture
def app():
    """Create test application with all blueprints."""
    test_app = Flask(__name__)
    test_app.config.from_object(Config)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(test_app)

    test_app.register_blueprint(genai_bp, url_prefix="/api/genai")
    test_app.register_blueprint(record_bp)
    test_app.register_blueprint(audit_bp)

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_conversation_endpoints_and_isolation(client, app):
    """Test conversation CRUD and verify separate session isolation (Screen B)."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # 1. Create Conversation A
    res_a = client.post("/api/genai/conversations", json={"title": "POSCO Case Inquiry"})
    assert res_a.status_code == 201
    conv_a_id = res_a.get_json()["id"]

    # 2. Create Conversation B
    res_b = client.post("/api/genai/conversations", json={"title": "General AI Chat"})
    assert res_b.status_code == 201
    conv_b_id = res_b.get_json()["id"]
    assert conv_a_id != conv_b_id

    # 3. List conversations
    res_list = client.get("/api/genai/conversations")
    assert res_list.status_code == 200
    conv_ids = [c["id"] for c in res_list.get_json()]
    assert conv_a_id in conv_ids
    assert conv_b_id in conv_ids

    # 4. User 2 cannot access Conversation A
    with client.session_transaction() as sess:
        sess["user_id"] = 2
    res_unauth = client.get(f"/api/genai/conversations/{conv_a_id}")
    assert res_unauth.status_code == 404


def test_posco_case_end_to_end_demonstration(client, app):
    """The central project scenario:
    1. HR employee submits confidential POSCO discussion in Conversation 1 for summary.
    2. Data is tracked with original purpose 'HR Investigation Summary'.
    3. In Conversation 2, user attempts to reuse confidential details for 'Marketing'.
    4. System detects reuse, blocks request, and NEVER sends data to AI provider.
    5. User reuses confidential details for same purpose 'HR Investigation Summary' -> ALLOW.
    """
    confidential_posco_data = (
        "CONFIDENTIAL HR RECORD: On October 14, the POSCO committee met to review "
        "testimony from witness A regarding incident #882 in the manufacturing division. "
        "Action agreed: strict nondisclosure and internal resolution."
    )

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # --- Step 1: Create Conversation 1 and submit POSCO data for summary ---
    res_conv1 = client.post("/api/genai/conversations", json={"title": "POSCO Inquiry #882"})
    conv1_id = res_conv1.get_json()["id"]

    res_step1 = client.post("/api/genai/generate", json={
        "user_id": "1",
        "conversation_id": conv1_id,
        "purpose": "HR Investigation Summary",
        "data_category": "HR",
        "prompt": f"Please summarize this document: {confidential_posco_data}",
        "track_as_record": True,
        "record_title": "POSCO Witness Testimony #882",
        "data_classification": "POSCO Confidential",
    })

    assert res_step1.status_code == 200
    data_step1 = res_step1.get_json()
    assert data_step1["decision"] == "ALLOW"
    assert data_step1["sent_to_provider"] is True

    # Verify protected record was created with immutable original purpose (Objectives 1 & 2)
    with app.app_context():
        records = ProtectedRecord.query.filter_by(user_id=1).all()
        assert len(records) == 1
        assert records[0].original_purpose == "HR Investigation Summary"
        assert records[0].data_classification == "POSCO Confidential"

    # --- Step 2: Start Conversation 2 (New Chat, separate context) ---
    res_conv2 = client.post("/api/genai/conversations", json={"title": "New Public Memo"})
    conv2_id = res_conv2.get_json()["id"]

    # Verify context isolation: Conversation 2 has 0 messages
    res_history = client.get(f"/api/genai/conversations/{conv2_id}")
    assert len(res_history.get_json()["messages"]) == 0

    # --- Step 3: Attempt to reuse confidential POSCO details for Marketing in Conversation 2 ---
    res_step3 = client.post("/api/genai/generate", json={
        "user_id": "1",
        "conversation_id": conv2_id,
        "purpose": "External Marketing Announcement",
        "data_category": "HR",
        "prompt": "Use witness A testimony regarding incident #882 in manufacturing to draft a public press release.",
    })

    assert res_step3.status_code == 200
    data_step3 = res_step3.get_json()

    # Must be BLOCKED
    assert data_step3["decision"] == "BLOCK"
    assert data_step3["authorized"] is False
    assert data_step3["reuse_detected"] is True
    assert data_step3["sent_to_provider"] is False  # Restricted data NEVER sent!
    assert "strictly prohibits" in data_step3["reason"]

    # --- Step 4: Attempt to reuse confidential details for an ambiguous purpose (WARN) ---
    res_step4 = client.post("/api/genai/generate", json={
        "user_id": "1",
        "conversation_id": conv2_id,
        "purpose": "Corporate Training Module",
        "data_category": "HR",
        "prompt": "Use incident #882 from the manufacturing division as a case study.",
    })

    assert res_step4.status_code == 200
    data_step4 = res_step4.get_json()
    assert data_step4["decision"] == "WARN"
    assert data_step4["requires_review"] is True
    assert data_step4["sent_to_provider"] is False  # Restricted data NEVER sent!

    # --- Step 5: Reuse confidential details for the SAME authorized purpose -> ALLOW ---
    res_step5 = client.post("/api/genai/generate", json={
        "user_id": "1",
        "conversation_id": conv2_id,
        "purpose": "HR Investigation Summary",
        "data_category": "HR",
        "prompt": "Summarize witness A testimony regarding incident #882 for our file.",
    })

    assert res_step5.status_code == 200
    data_step5 = res_step5.get_json()
    assert data_step5["decision"] == "ALLOW"
    assert data_step5["sent_to_provider"] is True

    # --- Step 6: Verify Audit History (Screen E & tamper-evidence) ---
    res_audit = client.get("/api/audit")
    assert res_audit.status_code == 200
    events = res_audit.get_json()
    decisions = [e["decision"] for e in events if e["decision"] != "—"]
    assert "BLOCK" in decisions
    assert "WARN" in decisions
    assert "ALLOW" in decisions

    # Verify that BLOCKED and WARNED events recorded sent_to_provider == False
    for event in events:
        if event["decision"] in ("BLOCK", "WARN"):
            assert event["sent_to_provider"] is False
