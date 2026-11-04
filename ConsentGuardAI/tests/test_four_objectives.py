"""
Comprehensive Verification Test Suite for the Four Official Objectives and 10 Mandated Test Cases.

PROJECT TITLE:
ConsentGuardAI: A Purpose-Based Authorization System for Secure Reuse of User Data in Generative AI

FOUR OFFICIAL OBJECTIVES:
Objective 1: To identify and track user data provided to the Generative AI system.
Objective 2: To record the original purpose for which the user data was provided.
Objective 3: To detect and analyze the reuse of previously provided user data in new requests.
Objective 4: To determine authorization by comparing the original purpose with the new purpose and generate an Allow / Warn / Block decision.

TEN MANDATED TEST CASES:
1. New request with no previously tracked data (ALLOW).
2. Data reuse for the same purpose (ALLOW).
3. Data reuse for a different purpose (WARN).
4. Reuse prohibited by policy (BLOCK).
5. Missing original-purpose information (BLOCK).
6. Reuse detection or authorization service failure (BLOCK fail-closed).
7. Isolation between different users.
8. Isolation between separate conversations.
9. Correct ALLOW, WARN, and BLOCK outcomes verified with full audit logging.
10. Verification that restricted data under WARN, BLOCK, or security check failure is NEVER sent to the AI provider.
"""

import os
import sys
import uuid
from unittest.mock import patch

# Ensure the root ConsentGuardAI directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from flask import Flask

from app import db
from app.config import Config
from app.routes.auth_routes import auth_bp
from app.routes.record_routes import record_bp
from app.routes.audit_routes import audit_bp
from app.routes.consent_routes import consent_bp
from app.routes.authorization_routes import authorization_bp
from app.routes.genai_routes import genai_bp
from database.models import User, ProtectedRecord, AuditLog, Conversation, ChatMessage
from database.repositories import (
    create_conversation,
    get_user_conversations,
    create_chat_message,
    get_conversation_messages,
    create_protected_record,
    get_user_protected_records,
    get_protected_record,
    get_dashboard_stats,
    get_audit_logs,
)
from consent.consent_repository import ConsentRepository
from consent.consent_service import ConsentService
from audit.audit_service import record_event
from audit.integrity import verify_audit_chain
from policy_engine.reuse_detector import DataReuseDetector, ReuseMatch
from policy_engine.purpose_engine import PurposeEngine
from policy_engine.policy_rules import PolicyRules
from policy_engine.authorization import AuthorizationService, AuthorizationDecision
from security.encryption import encrypt_data


@pytest.fixture
def app():
    """Create an isolated test application with an in-memory SQLite database."""
    test_app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
        static_url_path="/static",
    )
    test_app.config.from_object(Config)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="test-four-objectives-key",
        WTF_CSRF_ENABLED=False,
    )
    db.init_app(test_app)

    # Register all routes and blueprints
    test_app.register_blueprint(auth_bp)
    test_app.register_blueprint(record_bp)
    test_app.register_blueprint(audit_bp)
    test_app.register_blueprint(consent_bp)
    test_app.register_blueprint(authorization_bp)
    test_app.register_blueprint(genai_bp, url_prefix="/api/genai")

    from flask import render_template

    @test_app.route("/")
    def home():
        return render_template("index.html")

    @test_app.route("/chat")
    def chat_page():
        return render_template("chat.html")

    @test_app.route("/record")
    def record_page():
        return render_template("record.html")

    @test_app.route("/authorization")
    def auth_page():
        return render_template("authorization.html")

    @test_app.route("/audit")
    def audit_page():
        return render_template("audit.html")

    with test_app.app_context():
        db.create_all()
        # Seed test users
        u1 = User(id=1, email=f"hr_{uuid.uuid4().hex[:6]}@company.com", password_hash="hash1")
        u2 = User(id=2, email=f"other_{uuid.uuid4().hex[:6]}@company.com", password_hash="hash2")
        db.session.add_all([u1, u2])
        db.session.commit()
        yield test_app
        db.session.rollback()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_service():
    consent_repo = ConsentRepository()
    consent_svc = ConsentService(consent_repo)
    return AuthorizationService(
        consent_service=consent_svc,
        policy_rules=PolicyRules(PurposeEngine()),
        reuse_detector=DataReuseDetector(),
    )


# ============================================================================
# OBJECTIVE 1: TRACK USER DATA
# ============================================================================

def test_objective_1_track_and_store_user_data(app):
    """
    OBJECTIVE 1: Identify and track user data provided to the Generative AI system.
    Confidential user data is encrypted, linked to the user and conversation, and retrievable.
    """
    with app.app_context():
        conv = create_conversation(user_id=1, title="HR Case 2026-A")
        plaintext = "Confidential POSCO harassment incident report regarding Senior Manager X in Division 4."

        record = create_protected_record(
            user_id=1,
            title="POSCO Harassment Incident Report",
            data_encrypted=encrypt_data(plaintext).encode("utf-8"),
            original_purpose="HR Investigation Summary",
            data_classification="confidential",
            conversation_id=conv.id,
            description="POSCO Harassment Incident Report"
        )

        assert record.id is not None
        assert record.user_id == 1
        assert record.conversation_id == conv.id
        assert record.data_classification == "confidential"
        # Ciphertext must NOT match raw plaintext
        assert record.data_encrypted != plaintext.encode("utf-8")

        # Fetch records for user
        user_records = get_user_protected_records(user_id=1)
        assert len(user_records) == 1
        assert user_records[0].description == "POSCO Harassment Incident Report"


# ============================================================================
# OBJECTIVE 2: RECORD IMMUTABLE ORIGINAL PURPOSE
# ============================================================================

def test_objective_2_immutable_original_purpose(app):
    """
    OBJECTIVE 2: Record the original purpose for which the user data was provided.
    Preserves that purpose as an immutable reference that cannot be modified.
    """
    with app.app_context():
        conv = create_conversation(user_id=1, title="HR Session")
        plaintext = "Confidential disciplinary hearing transcript dated Oct 2026."
        record = create_protected_record(
            user_id=1,
            title="Disciplinary Hearing Transcript",
            data_encrypted=encrypt_data(plaintext).encode("utf-8"),
            original_purpose="HR Disciplinary Review",
            data_classification="confidential",
            conversation_id=conv.id
        )

        assert record.original_purpose == "HR Disciplinary Review"

        # Verify through DB query that original_purpose remains intact
        fetched = get_protected_record(record.id)
        assert fetched is not None
        assert fetched.original_purpose == "HR Disciplinary Review"


# ============================================================================
# TEN MANDATED TEST CASES (OBJECTIVES 3 & 4)
# ============================================================================

def test_case_1_new_request_no_tracked_data_allows(app, auth_service):
    """
    TEST CASE 1: New request with no previously tracked data (ALLOW).
    Fresh prompt with no historical data match should be safely ALLOWED.
    """
    with app.app_context():
        detector = DataReuseDetector()
        prompt = "Write a generic Python function to calculate fibonacci numbers."
        match = detector.detect_in_records(prompt=prompt, records=[])

        assert match.detected is False

        auth_result = auth_service.authorize_prompt_request(
            user_id="1",
            prompt=prompt,
            purpose="Code Generation",
            records=[]
        )
        assert auth_result.decision == "ALLOW"
        assert auth_result.reuse_detected is False
        assert "no previously stored data detected" in auth_result.reason.lower()


def test_case_2_data_reuse_same_purpose_allows(app, auth_service):
    """
    TEST CASE 2: Data reuse for the same purpose (ALLOW).
    When previously tracked confidential data is reused within the authorized original purpose,
    the system correctly detects reuse and grants ALLOW.
    """
    with app.app_context():
        conv = create_conversation(user_id=1, title="HR Conversation")
        sensitive_text = "POSCO harassment formal complaint lodged against Manager X by complainant Y on Oct 14."
        record = create_protected_record(
            user_id=1,
            title="POSCO Complaint Record",
            data_encrypted=encrypt_data(sensitive_text).encode("utf-8"),
            original_purpose="HR Investigation Summary",
            data_classification="confidential",
            conversation_id=conv.id
        )

        prompt = "Please draft the concluding section of the HR Investigation Summary regarding POSCO harassment formal complaint lodged against Manager X."
        records = get_user_protected_records(user_id=1)

        auth_result = auth_service.authorize_prompt_request(
            user_id="1",
            prompt=prompt,
            purpose="HR Investigation Summary",
            records=records
        )

        assert auth_result.reuse_detected is True
        assert auth_result.decision == "ALLOW"
        assert auth_result.matched_record_id == record.id
        assert "data reuse authorized" in auth_result.reason.lower()


def test_case_3_data_reuse_different_purpose_warns(app, auth_service):
    """
    TEST CASE 3: Data reuse for a different purpose (WARN).
    When confidential data is reused for a compatible or secondary purpose
    that is not explicitly prohibited, the system issues a WARN decision with explanation.
    """
    with app.app_context():
        conv = create_conversation(user_id=1, title="HR Case")
        sensitive_text = "Employee medical accommodation details and ergonomic assessment recommendations."
        record = create_protected_record(
            user_id=1,
            title="Medical Accommodation Record",
            data_encrypted=encrypt_data(sensitive_text).encode("utf-8"),
            original_purpose="Medical Accommodation Review",
            data_classification="confidential",
            conversation_id=conv.id
        )

        prompt = "Review the ergonomic assessment recommendations and employee medical accommodation details for internal training."
        records = get_user_protected_records(user_id=1)

        auth_result = auth_service.authorize_prompt_request(
            user_id="1",
            prompt=prompt,
            purpose="Internal Corporate Training",
            records=records
        )

        assert auth_result.reuse_detected is True
        assert auth_result.decision == "WARN"
        assert auth_result.matched_record_id == record.id
        assert auth_result.requires_review is True
        assert "restricted data held" in auth_result.reason.lower()


def test_case_4_reuse_prohibited_by_policy_blocks(app, auth_service):
    """
    TEST CASE 4: Reuse prohibited by policy (BLOCK).
    THE CORE REAL-WORLD POSCO SCENARIO:
    A user attempts to reuse confidential POSCO harassment inquiry text for
    External Marketing Announcement. System must strictly BLOCK the request.
    """
    with app.app_context():
        conv1 = create_conversation(user_id=1, title="Confidential POSCO Investigation")
        sensitive_posco = (
            "Confidential POSCO inquiry statement: Complainant Ms. K accused Director M of improper conduct "
            "during the internal Q3 audit conference at the regional office."
        )
        record = create_protected_record(
            user_id=1,
            title="POSCO Harassment Witness Transcript",
            data_encrypted=encrypt_data(sensitive_posco).encode("utf-8"),
            original_purpose="HR Investigation Summary",
            data_classification="confidential",
            conversation_id=conv1.id,
            description="POSCO Harassment Witness Transcript"
        )

        # In a new session, user asks for marketing announcement with sensitive details
        prompt_reuse = (
            "Draft a public press release and announcement stating: "
            "Complainant Ms. K accused Director M of improper conduct during the internal Q3 audit conference."
        )
        records = get_user_protected_records(user_id=1)

        auth_result = auth_service.authorize_prompt_request(
            user_id="1",
            prompt=prompt_reuse,
            purpose="External Marketing Announcement",
            records=records
        )

        assert auth_result.reuse_detected is True
        assert auth_result.decision == "BLOCK"
        assert auth_result.matched_record_id == record.id
        assert "prohibit" in auth_result.reason.lower() or "blocked" in auth_result.reason.lower()


def test_case_5_missing_original_purpose_blocks(auth_service):
    """
    TEST CASE 5: Missing original-purpose information (BLOCK).
    If a tracked record has no valid recorded purpose, policy must treat it as unverified
    and fail-closed with a BLOCK decision.
    """
    policy_rules = PolicyRules()
    match_no_purpose = ReuseMatch(
        detected=True,
        record_id=99,
        original_purpose=None,  # Missing original purpose
        match_type="partial",
        data_classification="confidential",
    )

    decision = policy_rules.evaluate_purpose_reuse(
        reuse_match=match_no_purpose,
        requested_purpose="Executive Briefing",
    )

    assert decision.decision == "BLOCK"
    assert decision.allowed is False
    assert "missing original purpose" in decision.reason.lower()


def test_case_6_fail_closed_on_detection_or_decryption_failure(app, auth_service):
    """
    TEST CASE 6: Reuse detection or authorization service failure (BLOCK fail-closed).
    If ciphertext is corrupted or decryption fails, the system must NEVER silently skip
    the record; it must immediately trigger a fail-closed BLOCK.
    """
    with app.app_context():
        conv = create_conversation(user_id=1, title="Corrupt Test")
        corrupt_rec = ProtectedRecord(
            user_id=1,
            title="Corrupted Record Test",
            data_encrypted=b"corrupted-unreadable-ciphertext-123456",
            original_purpose="Legal Compliance",
            data_classification="confidential",
            conversation_id=conv.id,
            description="Corrupted record test"
        )
        db.session.add(corrupt_rec)
        db.session.commit()

        records = get_user_protected_records(user_id=1)

        # Detector must report decryption failure
        detector = DataReuseDetector()
        match = detector.detect_in_records(prompt="Check compliance status.", records=records)
        assert match.decryption_failed is True
        assert match.match_type == "decryption_error"

        # PolicyRules must translate decryption_failed to BLOCK
        policy_rules = PolicyRules()
        decision = policy_rules.evaluate_purpose_reuse(
            reuse_match=match,
            requested_purpose="Legal Compliance",
        )
        assert decision.decision == "BLOCK"
        assert "Decryption failed" in decision.reason


def test_case_7_isolation_between_different_users(app, auth_service):
    """
    TEST CASE 7: Isolation between different users.
    User 1's protected records and conversation sessions must never be accessible,
    matched against, or visible to User 2.
    """
    with app.app_context():
        # User 1 stores secret HR note
        conv_a = create_conversation(user_id=1, title="HR Confidential")
        sensitive_text = "Special compensation package for Executive Officer Z: USD 500,000 bonus."
        create_protected_record(
            user_id=1,
            title="Executive Compensation Record",
            data_encrypted=encrypt_data(sensitive_text).encode("utf-8"),
            original_purpose="Executive Compensation",
            data_classification="confidential",
            conversation_id=conv_a.id
        )

        # User 2 queries about Executive Officer Z bonus
        detector = DataReuseDetector()
        user_2_records = get_user_protected_records(user_id=2)
        match_user_2 = detector.detect_in_records(
            prompt="Tell me about the special compensation package for Executive Officer Z: USD 500,000 bonus.",
            records=user_2_records
        )

        # User 2 has zero matches because User 1's data is isolated
        assert match_user_2.detected is False
        assert len(user_2_records) == 0

        # User 2 cannot see User 1's conversations
        user_2_convs = get_user_conversations(user_id=2)
        assert len(user_2_convs) == 0


def test_case_8_isolation_between_separate_conversations(app):
    """
    TEST CASE 8: Isolation between separate conversations.
    A new conversation session does NOT inherit or silently load message history
    from prior conversations.
    """
    with app.app_context():
        conv1 = create_conversation(user_id=1, title="Session 1 - Harassment Inquiry")
        create_chat_message(
            conversation_id=conv1.id,
            user_id=1,
            role="user",
            content="Complainant testimony regarding incident at the cafeteria.",
            purpose="HR Investigation Summary",
            decision="ALLOW"
        )
        create_chat_message(
            conversation_id=conv1.id,
            user_id=1,
            role="assistant",
            content="Summary: Witness observed altercation at 2:15 PM in cafeteria.",
            purpose="HR Investigation Summary",
            decision="ALLOW"
        )

        # Create Session 2
        conv2 = create_conversation(user_id=1, title="Session 2 - Performance Goals")

        # Session 2 must be completely empty of Session 1's messages
        messages_conv2 = get_conversation_messages(conv2.id)
        assert len(messages_conv2) == 0

        # Messages in Session 1 remain isolated
        messages_conv1 = get_conversation_messages(conv1.id)
        assert len(messages_conv1) == 2


def test_case_9_structured_audit_history_for_allow_warn_block(app):
    """
    TEST CASE 9: Correct ALLOW, WARN, and BLOCK outcomes with audit logging and hash integrity.
    Verifies that all three decisions are recorded in AuditLog with their full structured metadata,
    and that the cryptographic hash chain is verified.
    """
    with app.app_context():
        # Record ALLOW event
        record_event(
            event_type="GENAI_PROMPT_REQUEST",
            description="Authorized HR prompt execution",
            user_id=1,
            decision="ALLOW",
            original_purpose="HR Investigation Summary",
            requested_purpose="HR Investigation Summary",
            reuse_detected=True,
            sent_to_provider=True,
        )

        # Record WARN event
        record_event(
            event_type="GENAI_PROMPT_REQUEST",
            description="Cross-purpose reuse warning",
            user_id=1,
            decision="WARN",
            original_purpose="HR Investigation Summary",
            requested_purpose="Internal Knowledge Base",
            reuse_detected=True,
            sent_to_provider=False,
        )

        # Record BLOCK event
        record_event(
            event_type="GENAI_PROMPT_REQUEST",
            description="Policy violation block",
            user_id=1,
            decision="BLOCK",
            original_purpose="HR Investigation Summary",
            requested_purpose="External Marketing Announcement",
            reuse_detected=True,
            sent_to_provider=False,
        )

        recent_logs = get_audit_logs(limit=10)
        assert len(recent_logs) >= 3

        # Verify cryptographic integrity of the audit chain
        assert verify_audit_chain(recent_logs) is True

        # Verify dashboard statistics reflect the records
        stats = get_dashboard_stats()
        assert stats["decisions"]["ALLOW"] >= 1
        assert stats["decisions"]["WARN"] >= 1
        assert stats["decisions"]["BLOCK"] >= 1
        assert stats["reuse_attempts_detected"] >= 3


def test_case_10_gatekeeper_never_sends_restricted_data_on_warn_or_block(client, app):
    """
    TEST CASE 10: Verification that restricted data under WARN or BLOCK is NEVER sent to AI provider.
    Tests the Flask `/api/genai/generate` endpoint under ALLOW, WARN, and BLOCK conditions,
    asserting that `gateway.generate` is strictly NEVER called when the decision is WARN or BLOCK.
    """
    with app.app_context():
        conv = create_conversation(user_id=1, title="Confidential Case")
        conv_id = conv.id
        sensitive_posco = (
            "POSCO confidential interview findings: Accused manager admitted to sending inappropriate "
            "messages during project sprint review."
        )
        create_protected_record(
            user_id=1,
            title="POSCO Sprint Review Interview",
            data_encrypted=encrypt_data(sensitive_posco).encode("utf-8"),
            original_purpose="HR Investigation Summary",
            data_classification="confidential",
            conversation_id=conv_id
        )

    # Log in as user 1
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["email"] = "hr@company.com"

    # Part A: Test BLOCK scenario (External Marketing)
    with patch("app.routes.genai_routes.gateway.generate") as mock_generate:
        block_prompt = (
            "Publish this to our social channels: Accused manager admitted to sending inappropriate "
            "messages during project sprint review."
        )
        response = client.post("/api/genai/generate", json={
            "user_id": "1",
            "prompt": block_prompt,
            "purpose": "External Marketing Announcement",
            "data_category": "HR",
            "conversation_id": conv_id
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["decision"] == "BLOCK"
        assert data["sent_to_provider"] is False
        # CRITICAL VERIFICATION: Gateway model MUST NOT have been called!
        mock_generate.assert_not_called()

    # Part B: Test WARN scenario (Secondary Facilities Review)
    with patch("app.routes.genai_routes.gateway.generate") as mock_generate:
        warn_prompt = (
            "Incorporate into facilities guidelines: Accused manager admitted to sending inappropriate "
            "messages during project sprint review."
        )
        response = client.post("/api/genai/generate", json={
            "user_id": "1",
            "prompt": warn_prompt,
            "purpose": "General Facilities Guidelines",
            "data_category": "HR",
            "conversation_id": conv_id
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["decision"] == "WARN"
        assert data["sent_to_provider"] is False
        # CRITICAL VERIFICATION: Gateway model MUST NOT have been called for WARN!
        mock_generate.assert_not_called()

    # Part C: Test ALLOW scenario (Authorized Original Purpose)
    with patch("app.routes.genai_routes.gateway.generate", return_value={"success": True, "response": "Summary finalized."}) as mock_generate:
        allow_prompt = (
            "Format the HR Investigation Summary: Accused manager admitted to sending inappropriate "
            "messages during project sprint review."
        )
        response = client.post("/api/genai/generate", json={
            "user_id": "1",
            "prompt": allow_prompt,
            "purpose": "HR Investigation Summary",
            "data_category": "HR",
            "conversation_id": conv_id
        })

        assert response.status_code == 200
        data = response.get_json()
        assert data["decision"] == "ALLOW"
        assert data["sent_to_provider"] is True
        # Gateway model is ONLY called when decision is ALLOW
        mock_generate.assert_called_once()


# ============================================================================
# FRONTEND ROUTE RENDERING & LIVE BACKEND API VERIFICATION
# ============================================================================

def test_frontend_screens_render_and_serve_real_data(client, app):
    """
    Verify all 5 frontend screens render successfully and connect to backend data:
    Screen A: / (Privacy Dashboard)
    Screen B: /chat (AI Chat)
    Screen C: /record (Data Tracking)
    Screen D: /authorization (Reuse Detection and Authorization)
    Screen E: /audit (Decision History and Audit)
    """
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["email"] = "hr@company.com"

    # Screen A: Dashboard
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Privacy Dashboard" in resp.data

    # Screen B: Chat
    resp = client.get("/chat")
    assert resp.status_code == 200
    assert b"AI Assistant" in resp.data or b"New Conversation" in resp.data

    # Screen C: Records
    resp = client.get("/record")
    assert resp.status_code == 200
    assert b"Data Tracking" in resp.data

    # Screen D: Authorization Policy Inspector
    resp = client.get("/authorization")
    assert resp.status_code == 200
    assert b"Reuse Detection" in resp.data or b"Authorization" in resp.data

    # Screen E: Audit & Integrity
    resp = client.get("/audit")
    assert resp.status_code == 200
    assert b"Decision History" in resp.data

    # API Endpoint: Dashboard Stats
    resp_stats = client.get("/api/audit/stats")
    assert resp_stats.status_code == 200
    stats_data = resp_stats.get_json()
    assert "records_with_original_purpose" in stats_data
    assert "reuse_attempts_detected" in stats_data
    assert "decisions" in stats_data

    # API Endpoint: Authorization Inspect tool (Screen D)
    resp_inspect = client.post("/api/authorization/inspect", json={
        "prompt": "Summarize POSCO case details.",
        "purpose": "External Marketing Announcement"
    })
    assert resp_inspect.status_code == 200
    inspect_data = resp_inspect.get_json()
    assert "decision" in inspect_data
    assert "reason" in inspect_data
