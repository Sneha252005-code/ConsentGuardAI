"""Tests verifying the fixes for:
1. Actual AI answer display on ALLOW.
2. Reuse detection for original purpose (ALLOW).
3. Reuse detection for public advertisement (BLOCK).
4. Paraphrased version of previously tracked data detection.
5. Completely unrelated questions receive ALLOW and genuine AI answers.
6. Confirmation that restricted data is strictly NEVER sent on WARN or BLOCK.
"""

from unittest.mock import patch
import pytest
from flask import Flask

from app import db
from app.config import Config
from app.routes.genai_routes import genai_bp
from app.routes.authorization_routes import authorization_bp
from app.routes.record_routes import record_bp
from app.routes.audit_routes import audit_bp
from database.models import User, ProtectedRecord, Conversation
from database.repositories import create_conversation, create_protected_record, get_user_protected_records
from genai_gateway.provider_client import generate_intelligent_response, MockProvider
from policy_engine.reuse_detector import DataReuseDetector
from security.encryption import encrypt_data


@pytest.fixture
def app():
    test_app = Flask(__name__)
    test_app.config.from_object(Config)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(test_app)

    test_app.register_blueprint(genai_bp, url_prefix="/api/genai")
    test_app.register_blueprint(authorization_bp)
    test_app.register_blueprint(record_bp)
    test_app.register_blueprint(audit_bp)

    with test_app.app_context():
        db.create_all()
        # Seed test user
        u = User(id=1, email="evaluator@consentguard.ai", password_hash="hashedpass123")
        db.session.add(u)
        db.session.commit()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Test 1: Normal unrelated question receives actual AI answer after ALLOW
# ---------------------------------------------------------------------------

def test_1_normal_unrelated_question_receives_actual_ai_answer(client, app):
    """A normal unrelated question receives an actual AI answer after ALLOW, not a canned stub."""
    with client.session_transaction() as sess:
        sess["user_id"] = 1

    prompt = "What is the capital of France?"
    res = client.post("/api/genai/generate", json={
        "user_id": "1",
        "prompt": prompt,
        "purpose": "General Knowledge Inquiry",
        "data_category": "General",
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data["decision"] == "ALLOW"
    assert data["authorized"] is True
    assert data["sent_to_provider"] is True
    # Verify response contains the actual AI answer
    assert "Paris" in data["response"]
    assert "Response generated securely for purpose" not in data["response"]


# ---------------------------------------------------------------------------
# Test 2: Reuse of employee training info for its original purpose (ALLOW)
# ---------------------------------------------------------------------------

def test_2_reuse_employee_training_original_purpose(client, app):
    """Reuse of employee training information for its original purpose produces ALLOW."""
    with app.app_context():
        conv = create_conversation(user_id=1, title="HR Training Records")
        training_text = "Fictional employee training is scheduled for Monday at 10 AM in Conference Room B."
        rec = create_protected_record(
            user_id=1,
            title="Employee Training Schedule",
            data_encrypted=encrypt_data(training_text).encode("utf-8"),
            original_purpose="Internal employee training",
            data_classification="Confidential",
            conversation_id=conv.id,
            description="Notes about an employee training schedule",
        )
        rec_id = rec.id

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    prompt = "Please format the notes for our employee training schedule on Monday at 10 AM."
    res = client.post("/api/genai/generate", json={
        "user_id": "1",
        "prompt": prompt,
        "purpose": "Internal employee training",
        "data_category": "HR",
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data["decision"] == "ALLOW"
    assert data["reuse_detected"] is True
    assert data["matched_record_id"] == rec_id
    assert data["sent_to_provider"] is True
    assert "data reuse authorized" in data["reason"].lower()


# ---------------------------------------------------------------------------
# Test 3: Reuse of employee training info for public advertisement (BLOCK)
# ---------------------------------------------------------------------------

def test_3_reuse_employee_training_for_public_advertisement_blocks(client, app):
    """Reuse of the employee training schedule in a public advertisement is detected and BLOCKED."""
    with app.app_context():
        conv = create_conversation(user_id=1, title="Training Session")
        training_text = "Fictional employee training is scheduled for Monday at 10 AM."
        rec = create_protected_record(
            user_id=1,
            title="Employee Training Schedule",
            data_encrypted=encrypt_data(training_text).encode("utf-8"),
            original_purpose="Internal employee training",
            data_classification="Confidential",
            conversation_id=conv.id,
            description="Notes about an employee training schedule",
        )
        rec_id = rec.id

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # Inspector check (Screen D)
    res_inspect = client.post("/api/authorization/inspect", json={
        "prompt": "Use the employee training schedule in a public advertisement.",
        "purpose": "External Marketing Announcement",
        "data_category": "HR",
    })
    assert res_inspect.status_code == 200
    data_inspect = res_inspect.get_json()
    assert data_inspect["reuse_detected"] is True
    assert data_inspect["matched_record_id"] == rec_id
    assert data_inspect["decision"] == "BLOCK"
    assert "strictly prohibits" in data_inspect["reason"].lower()

    # Chat route check (Screen B)
    res_chat = client.post("/api/genai/generate", json={
        "user_id": "1",
        "prompt": "Use the employee training schedule in a public advertisement.",
        "purpose": "External Marketing Announcement",
        "data_category": "HR",
    })
    assert res_chat.status_code == 200
    data_chat = res_chat.get_json()
    assert data_chat["decision"] == "BLOCK"
    assert data_chat["sent_to_provider"] is False


# ---------------------------------------------------------------------------
# Test 4: Paraphrased version of previously tracked information
# ---------------------------------------------------------------------------

def test_4_paraphrased_tracked_information_detected(client, app):
    """Paraphrased version using synonyms (staff coaching timetable) is detected as reuse."""
    with app.app_context():
        conv = create_conversation(user_id=1, title="Staff Coaching")
        training_text = "Fictional employee training is scheduled for Monday at 10 AM."
        rec = create_protected_record(
            user_id=1,
            title="Employee Training Schedule",
            data_encrypted=encrypt_data(training_text).encode("utf-8"),
            original_purpose="Internal employee training",
            data_classification="Confidential",
            conversation_id=conv.id,
            description="Notes about an employee training schedule",
        )
        rec_id = rec.id

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # Paraphrased prompt using enterprise synonyms
    paraphrase_prompt = "When is the staff coaching timetable taking place on Monday?"
    res = client.post("/api/authorization/inspect", json={
        "prompt": paraphrase_prompt,
        "purpose": "External Marketing Announcement",
        "data_category": "HR",
    })

    assert res.status_code == 200
    data = res.get_json()
    assert data["reuse_detected"] is True
    assert data["matched_record_id"] == rec_id
    assert data["decision"] == "BLOCK"


# ---------------------------------------------------------------------------
# Test 5: Completely unrelated questions receive ALLOW and NO false match
# ---------------------------------------------------------------------------

def test_5_completely_unrelated_questions_have_zero_false_matches(client, app):
    """Completely unrelated questions do not trigger false reuse matches and receive AI answers."""
    with app.app_context():
        conv = create_conversation(user_id=1, title="Staff Training")
        training_text = "Fictional employee training is scheduled for Monday at 10 AM."
        create_protected_record(
            user_id=1,
            title="Employee Training Schedule",
            data_encrypted=encrypt_data(training_text).encode("utf-8"),
            original_purpose="Internal employee training",
            data_classification="Confidential",
            conversation_id=conv.id,
            description="Notes about an employee training schedule",
        )

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    unrelated_prompts = [
        "Explain three ways a company can improve employee training. Give a short example for each.",
        "Write a Python function to sort a list.",
        "Explain how photosynthesis works in green plants.",
    ]

    for p in unrelated_prompts:
        res = client.post("/api/genai/generate", json={
            "user_id": "1",
            "prompt": p,
            "purpose": "General Knowledge Inquiry",
            "data_category": "General",
        })
        assert res.status_code == 200
        data = res.get_json()
        assert data["decision"] == "ALLOW"
        assert data["sent_to_provider"] is True
        # Actual AI content returned
        assert len(data["response"]) > 30


# ---------------------------------------------------------------------------
# Test 6: Confirmation restricted data is NOT sent on WARN or BLOCK
# ---------------------------------------------------------------------------

def test_6_restricted_data_never_sent_on_warn_or_block(client, app):
    """Verification that under WARN or BLOCK, gateway.generate is strictly NEVER called."""
    with app.app_context():
        conv = create_conversation(user_id=1, title="Confidential POSCO Inquiry")
        posco_data = "POSCO harassment formal complaint lodged against Manager X by employee Y."
        create_protected_record(
            user_id=1,
            title="POSCO Formal Complaint Record",
            data_encrypted=encrypt_data(posco_data).encode("utf-8"),
            original_purpose="HR Investigation Summary",
            data_classification="Confidential",
            conversation_id=conv.id,
        )

    with client.session_transaction() as sess:
        sess["user_id"] = 1

    # Case A: BLOCK (Marketing) -> mock gateway MUST NOT be called
    with patch("app.routes.genai_routes.gateway.generate") as mock_generate:
        res_block = client.post("/api/genai/generate", json={
            "user_id": "1",
            "prompt": "Publish to external media: POSCO harassment formal complaint lodged against Manager X.",
            "purpose": "External Marketing Announcement",
            "data_category": "HR",
        })
        assert res_block.status_code == 200
        data_block = res_block.get_json()
        assert data_block["decision"] == "BLOCK"
        assert data_block["sent_to_provider"] is False
        mock_generate.assert_not_called()

    # Case B: WARN (Secondary Facilities Training) -> mock gateway MUST NOT be called
    with patch("app.routes.genai_routes.gateway.generate") as mock_generate:
        res_warn = client.post("/api/genai/generate", json={
            "user_id": "1",
            "prompt": "Review for general facilities guidelines: POSCO harassment formal complaint lodged against Manager X.",
            "purpose": "Corporate Training Module",
            "data_category": "HR",
        })
        assert res_warn.status_code == 200
        data_warn = res_warn.get_json()
        assert data_warn["decision"] == "WARN"
        assert data_warn["sent_to_provider"] is False
        mock_generate.assert_not_called()
