"""Database repository functions for ConsentGuardAI."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from app import db
from database.models import (
    ConsentModel,
    ProtectedRecord,
    AuditLog,
    Conversation,
    ChatMessage,
)


class ConsentDatabaseRepository:
    """Persist and retrieve consent records using SQLAlchemy."""

    @staticmethod
    def _validate_text(value: str, field_name: str) -> str:
        """Validate and normalize a required text value."""
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def create(
        self,
        *,
        user_id: str,
        purpose: str,
        data_categories: list[str],
        consent_id: Optional[str] = None,
    ) -> ConsentModel:
        """Create and persist a consent record."""
        user_id = self._validate_text(user_id, "user_id")
        purpose = self._validate_text(purpose, "purpose")

        if not isinstance(data_categories, (list, tuple)) or not data_categories:
            raise ValueError(
                "data_categories must contain at least one category."
            )

        categories = list(dict.fromkeys(
            self._validate_text(category, "data_category")
            for category in data_categories
        ))

        if consent_id is None:
            consent_id = str(uuid.uuid4())
        else:
            consent_id = self._validate_text(consent_id, "consent_id")

        record = ConsentModel(
            id=consent_id,
            user_id=user_id,
            purpose=purpose,
            data_categories=categories,
            granted=True,
            version=1,
        )

        try:
            db.session.add(record)
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        return record

    def get(self, consent_id: str) -> Optional[ConsentModel]:
        """Retrieve a consent record by ID."""
        return db.session.get(ConsentModel, consent_id)

    def list_for_user(self, user_id: str) -> list[ConsentModel]:
        """List all consent records belonging to a user."""
        return ConsentModel.query.filter_by(user_id=user_id).all()

    def find_active(
        self,
        *,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> Optional[ConsentModel]:
        """Find active consent matching user, purpose, and category."""
        records = ConsentModel.query.filter_by(
            user_id=user_id,
            purpose=purpose,
            granted=True,
            withdrawn_at=None,
        ).all()

        for record in records:
            if data_category in (record.data_categories or []):
                return record

        return None

    def withdraw(self, consent_id: str) -> ConsentModel:
        """Withdraw consent; repeated withdrawals are safe."""
        record = self.get(consent_id)

        if record is None:
            raise KeyError(f"Consent record not found: {consent_id}")

        if record.granted or record.withdrawn_at is None:
            now = datetime.now(timezone.utc)
            record.granted = False
            record.withdrawn_at = record.withdrawn_at or now
            record.updated_at = now
            record.version += 1

            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise

        return record


# ---------------------------------------------------------------------------
# Conversation & Chat Message Repositories (Screen B - Isolated Sessions)
# ---------------------------------------------------------------------------

def create_conversation(
    user_id: int,
    title: str = "New Conversation",
    conversation_id: Optional[str] = None,
) -> Conversation:
    """Create a separate conversation session with isolated context."""
    conv_id = conversation_id or str(uuid.uuid4())
    conversation = Conversation(
        id=conv_id,
        user_id=int(user_id),
        title=(title or "New Conversation").strip()[:255],
    )
    db.session.add(conversation)
    db.session.commit()
    return conversation


def get_conversation(conversation_id: str) -> Optional[Conversation]:
    """Retrieve a conversation session by its unique ID."""
    if not conversation_id:
        return None
    return db.session.get(Conversation, str(conversation_id))


def get_user_conversations(user_id: int) -> list[Conversation]:
    """Retrieve all conversations belonging to a user in reverse chronological order."""
    return (
        Conversation.query
        .filter_by(user_id=int(user_id))
        .order_by(Conversation.updated_at.desc())
        .all()
    )


def update_conversation_title(
    conversation_id: str,
    title: str,
    user_id: Optional[int] = None,
) -> Optional[Conversation]:
    """Update conversation title."""
    conversation = get_conversation(conversation_id)
    if not conversation:
        return None
    if user_id is not None and conversation.user_id != int(user_id):
        return None
    conversation.title = (title or "New Conversation").strip()[:255]
    conversation.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return conversation


def delete_conversation(conversation_id: str, user_id: Optional[int] = None) -> bool:
    """Delete a conversation and all its contained messages."""
    conversation = get_conversation(conversation_id)
    if not conversation:
        return False
    if user_id is not None and conversation.user_id != int(user_id):
        return False
    db.session.delete(conversation)
    db.session.commit()
    return True


def create_chat_message(
    conversation_id: str,
    user_id: int,
    role: str,
    content: str,
    purpose: Optional[str] = None,
    decision: Optional[str] = None,
    decision_reason: Optional[str] = None,
) -> ChatMessage:
    """Save an individual chat message to the conversation session."""
    conversation = get_conversation(conversation_id)
    if not conversation:
        raise ValueError(f"Conversation {conversation_id} does not exist.")

    message = ChatMessage(
        conversation_id=conversation_id,
        user_id=int(user_id),
        role=role.strip(),
        content=content.strip(),
        purpose=purpose.strip() if purpose else None,
        decision=decision.strip().upper() if decision else None,
        decision_reason=decision_reason.strip() if decision_reason else None,
    )
    db.session.add(message)
    conversation.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return message


def get_conversation_messages(
    conversation_id: str,
    user_id: Optional[int] = None,
) -> list[ChatMessage]:
    """Get all messages for a conversation ensuring user isolation."""
    conversation = get_conversation(conversation_id)
    if not conversation:
        return []
    if user_id is not None and conversation.user_id != int(user_id):
        return []
    return (
        ChatMessage.query
        .filter_by(conversation_id=conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


# ---------------------------------------------------------------------------
# Protected Record Repositories (Objectives 1 & 2, Screen C)
# ---------------------------------------------------------------------------

def create_protected_record(
    user_id: int,
    title: str,
    data_encrypted: bytes,
    original_purpose: str,
    conversation_id: Optional[str] = None,
    description: Optional[str] = None,
    data_classification: str = "Confidential",
) -> ProtectedRecord:
    """Create and persist a tracked user data record with immutable original purpose."""
    if not original_purpose or not original_purpose.strip():
        raise ValueError("original_purpose is required and cannot be empty.")

    record = ProtectedRecord(
        user_id=int(user_id),
        title=title.strip()[:200],
        data_encrypted=data_encrypted,
        original_purpose=original_purpose.strip()[:500],
        conversation_id=conversation_id.strip() if conversation_id else None,
        description=description.strip()[:500] if description else None,
        data_classification=(data_classification or "Confidential").strip()[:100],
    )
    db.session.add(record)
    db.session.commit()
    return record


def get_protected_record(record_id: int) -> Optional[ProtectedRecord]:
    """Retrieve a protected record by its ID."""
    return db.session.get(ProtectedRecord, int(record_id))


def get_user_protected_records(user_id: int) -> list[ProtectedRecord]:
    """Retrieve all protected records belonging to a user (user isolation)."""
    return (
        ProtectedRecord.query
        .filter_by(user_id=int(user_id))
        .order_by(ProtectedRecord.created_at.desc())
        .all()
    )


def delete_protected_record(record_id: int) -> bool:
    """Delete a protected record by its ID."""
    record = get_protected_record(record_id)
    if record is None:
        return False
    db.session.delete(record)
    db.session.commit()
    return True


# ---------------------------------------------------------------------------
# Audit Log Repositories (Objective 4 & Screen E)
# ---------------------------------------------------------------------------

def create_audit_log(
    event_type: str,
    description: str,
    user_id: Optional[int] = None,
    previous_hash: Optional[str] = None,
    entry_hash: Optional[str] = None,
    conversation_id: Optional[str] = None,
    request_ref: Optional[str] = None,
    reuse_detected: bool = False,
    matched_record_id: Optional[int] = None,
    original_purpose: Optional[str] = None,
    requested_purpose: Optional[str] = None,
    decision: Optional[str] = None,
    decision_reason: Optional[str] = None,
    sent_to_provider: bool = False,
) -> AuditLog:
    """Create and save an audit log entry with structured decision history."""
    log = AuditLog(
        user_id=int(user_id) if user_id is not None else None,
        conversation_id=conversation_id,
        request_ref=request_ref,
        event_type=event_type.strip(),
        description=description.strip(),
        reuse_detected=bool(reuse_detected),
        matched_record_id=int(matched_record_id) if matched_record_id is not None else None,
        original_purpose=original_purpose.strip() if original_purpose else None,
        requested_purpose=requested_purpose.strip() if requested_purpose else None,
        decision=decision.strip().upper() if decision else None,
        decision_reason=decision_reason.strip() if decision_reason else None,
        sent_to_provider=bool(sent_to_provider),
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )
    db.session.add(log)
    db.session.commit()
    return log


def get_audit_logs(limit: int = 100, user_id: Optional[int] = None) -> list[AuditLog]:
    """Retrieve recent audit logs in reverse chronological order."""
    query = AuditLog.query
    if user_id is not None:
        query = query.filter_by(user_id=int(user_id))
    return query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(limit).all()


# ---------------------------------------------------------------------------
# Privacy Dashboard Real Data Aggregation (Screen A - Non-fabricated)
# ---------------------------------------------------------------------------

def get_dashboard_stats(user_id: Optional[int] = None) -> dict:
    """Aggregate real database statistics for the Privacy Dashboard."""
    record_query = ProtectedRecord.query
    audit_query = AuditLog.query

    if user_id is not None:
        record_query = record_query.filter_by(user_id=int(user_id))
        audit_query = audit_query.filter_by(user_id=int(user_id))

    total_records = record_query.count()
    records_with_purpose = (
        record_query
        .filter(ProtectedRecord.original_purpose.isnot(None))
        .filter(ProtectedRecord.original_purpose != "")
        .count()
    )

    # Count real reuse attempts detected
    reuse_attempts = (
        audit_query
        .filter(
            (AuditLog.reuse_detected == True) |  # noqa: E712
            (AuditLog.event_type == "DATA_REUSE_DETECTED")
        )
        .count()
    )

    # Count real decisions
    allow_count = audit_query.filter(AuditLog.decision == "ALLOW").count()
    warn_count = audit_query.filter(AuditLog.decision == "WARN").count()
    block_count = audit_query.filter(AuditLog.decision == "BLOCK").count()

    # Recent reuse attempts with real outcomes
    recent_reuse_logs = (
        audit_query
        .filter(
            (AuditLog.reuse_detected == True) |  # noqa: E712
            (AuditLog.event_type == "DATA_REUSE_DETECTED")
        )
        .order_by(AuditLog.created_at.desc())
        .limit(10)
        .all()
    )

    recent_reuse_events = [
        {
            "id": log.id,
            "timestamp": log.created_at.isoformat() if log.created_at else "",
            "request_ref": log.request_ref or f"REQ-{log.id}",
            "matched_record_id": log.matched_record_id,
            "original_purpose": log.original_purpose or "—",
            "requested_purpose": log.requested_purpose or "—",
            "decision": log.decision or "WARN",
            "decision_reason": log.decision_reason or log.description,
            "sent_to_provider": bool(log.sent_to_provider),
        }
        for log in recent_reuse_logs
    ]

    return {
        "total_records_tracked": total_records,
        "records_with_original_purpose": records_with_purpose,
        "reuse_attempts_detected": reuse_attempts,
        "decisions": {
            "ALLOW": allow_count,
            "WARN": warn_count,
            "BLOCK": block_count,
        },
        "recent_reuse_events": recent_reuse_events,
    }
