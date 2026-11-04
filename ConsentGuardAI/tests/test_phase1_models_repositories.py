"""Phase 1 tests: Database models, repositories, and context isolation."""

import pytest
from flask import Flask

from app import db
from app.config import Config
from database.models import (
    User,
    Conversation,
    ChatMessage,
    ProtectedRecord,
    AuditLog,
)
from database.repositories import (
    create_conversation,
    get_conversation,
    get_user_conversations,
    update_conversation_title,
    delete_conversation,
    create_chat_message,
    get_conversation_messages,
    create_protected_record,
    get_protected_record,
    get_user_protected_records,
    create_audit_log,
    get_audit_logs,
    get_dashboard_stats,
)
from audit.audit_service import record_event
from audit.integrity import verify_audit_chain


@pytest.fixture
def app():
    """Create an isolated test application."""
    test_app = Flask(__name__)
    test_app.config.from_object(Config)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(test_app)

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def test_conversation_lifecycle_and_user_isolation(app):
    """Verify separate conversation sessions and user isolation (Screen B)."""
    with app.app_context():
        # User 1 creates two conversations
        conv1 = create_conversation(user_id=1, title="HR Investigation 1")
        conv2 = create_conversation(user_id=1, title="HR Investigation 2")

        # User 2 creates one conversation
        conv3 = create_conversation(user_id=2, title="User 2 Secret Chat")

        user1_convs = get_user_conversations(user_id=1)
        assert len(user1_convs) == 2
        user1_ids = {c.id for c in user1_convs}
        assert conv1.id in user1_ids
        assert conv2.id in user1_ids
        assert conv3.id not in user1_ids

        # User 2 only sees their conversation
        user2_convs = get_user_conversations(user_id=2)
        assert len(user2_convs) == 1
        assert user2_convs[0].id == conv3.id

        # Update title
        updated = update_conversation_title(conv1.id, "Updated HR Case Title", user_id=1)
        assert updated.title == "Updated HR Case Title"

        # User 2 cannot update User 1's conversation
        unauthorized_update = update_conversation_title(conv1.id, "Hacked Title", user_id=2)
        assert unauthorized_update is None


def test_chat_messages_isolated_per_conversation(app):
    """Verify messages belong strictly to their conversation session."""
    with app.app_context():
        conv_a = create_conversation(user_id=1, title="Case A")
        conv_b = create_conversation(user_id=1, title="Case B")

        msg_a = create_chat_message(
            conversation_id=conv_a.id,
            user_id=1,
            role="user",
            content="Confidential POSCO inquiry details",
            purpose="HR Investigation Summary",
        )
        msg_a_reply = create_chat_message(
            conversation_id=conv_a.id,
            user_id=1,
            role="assistant",
            content="Summary of inquiry details...",
            purpose="HR Investigation Summary",
            decision="ALLOW",
        )

        # Messages in conv_a
        msgs_a = get_conversation_messages(conv_a.id, user_id=1)
        assert len(msgs_a) == 2
        assert msgs_a[0].content == "Confidential POSCO inquiry details"
        assert msgs_a[1].decision == "ALLOW"

        # conv_b must be empty — no context leakage
        msgs_b = get_conversation_messages(conv_b.id, user_id=1)
        assert len(msgs_b) == 0


def test_protected_record_metadata_and_immutable_purpose(app):
    """Verify Objective 1 & 2: tracking user data and freezing original purpose."""
    with app.app_context():
        record = create_protected_record(
            user_id=1,
            title="POSCO Committee Minutes",
            data_encrypted=b"encrypted_binary_content",
            original_purpose="HR Investigation Summary",
            conversation_id="conv-session-123",
            description="POSCO hearing notes regarding complaint #402",
            data_classification="POSCO Confidential",
        )

        assert record.id is not None
        assert record.user_id == 1
        assert record.conversation_id == "conv-session-123"
        assert record.title == "POSCO Committee Minutes"
        assert record.data_classification == "POSCO Confidential"
        assert record.original_purpose == "HR Investigation Summary"
        assert record.description == "POSCO hearing notes regarding complaint #402"

        # Re-fetch from DB
        fetched = get_protected_record(record.id)
        assert fetched.original_purpose == "HR Investigation Summary"

        # Attempting to create record without purpose must fail
        with pytest.raises(ValueError):
            create_protected_record(
                user_id=1,
                title="Invalid Record",
                data_encrypted=b"content",
                original_purpose="",
            )


def test_structured_audit_history_and_integrity_chain(app):
    """Verify Objective 4 and Screen E: structured audit events and tamper-evidence."""
    with app.app_context():
        log1 = record_event(
            event_type="RECORD_TRACKED",
            description="Tracked new confidential HR statement",
            user_id=1,
            conversation_id="conv-1",
            request_ref="REQ-001",
            original_purpose="HR Investigation Summary",
            decision="ALLOW",
            sent_to_provider=True,
        )

        log2 = record_event(
            event_type="DATA_REUSE_DETECTED",
            description="Reuse detected in new conversation for Marketing",
            user_id=1,
            conversation_id="conv-2",
            request_ref="REQ-002",
            reuse_detected=True,
            matched_record_id=1,
            original_purpose="HR Investigation Summary",
            requested_purpose="Marketing External Memo",
            decision="BLOCK",
            decision_reason="Policy strictly prohibits external reuse of POSCO records.",
            sent_to_provider=False,
        )

        logs = get_audit_logs(limit=10, user_id=1)
        assert len(logs) == 2

        # Verify hash integrity chain
        assert verify_audit_chain(logs) is True

        # Verify structured attributes
        assert logs[0].decision == "BLOCK"
        assert logs[0].reuse_detected is True
        assert logs[0].sent_to_provider is False
        assert logs[0].requested_purpose == "Marketing External Memo"


def test_privacy_dashboard_live_statistics(app):
    """Verify Screen A: live database-backed metrics without fabrication."""
    with app.app_context():
        # Setup real records
        create_protected_record(
            user_id=1,
            title="Doc 1",
            data_encrypted=b"data1",
            original_purpose="HR Review",
        )
        create_protected_record(
            user_id=1,
            title="Doc 2",
            data_encrypted=b"data2",
            original_purpose="Legal Audit",
        )

        # Setup real audit logs
        record_event(
            event_type="GENERATION_ALLOWED",
            description="Allowed same purpose",
            user_id=1,
            decision="ALLOW",
            sent_to_provider=True,
        )
        record_event(
            event_type="DATA_REUSE_DETECTED",
            description="Reuse detected with purpose conflict",
            user_id=1,
            reuse_detected=True,
            matched_record_id=1,
            original_purpose="HR Review",
            requested_purpose="Public Blog",
            decision="WARN",
            sent_to_provider=False,
        )
        record_event(
            event_type="DATA_REUSE_DETECTED",
            description="Prohibited reuse blocked",
            user_id=1,
            reuse_detected=True,
            matched_record_id=1,
            original_purpose="HR Review",
            requested_purpose="Commercial Sale",
            decision="BLOCK",
            sent_to_provider=False,
        )

        stats = get_dashboard_stats(user_id=1)
        assert stats["total_records_tracked"] == 2
        assert stats["records_with_original_purpose"] == 2
        assert stats["reuse_attempts_detected"] == 2
        assert stats["decisions"]["ALLOW"] == 1
        assert stats["decisions"]["WARN"] == 1
        assert stats["decisions"]["BLOCK"] == 1
        assert len(stats["recent_reuse_events"]) == 2
