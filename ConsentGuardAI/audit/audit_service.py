"""Audit logging service for ConsentGuardAI."""

from datetime import datetime, timezone

from database.models import AuditLog
from database.repositories import create_audit_log, get_audit_logs
from audit.integrity import calculate_entry_hash


def record_event(
    event_type: str,
    description: str,
    user_id=None,
    conversation_id=None,
    request_ref=None,
    reuse_detected=False,
    matched_record_id=None,
    original_purpose=None,
    requested_purpose=None,
    decision=None,
    decision_reason=None,
    sent_to_provider=False,
):
    """Record a security or authorization event with an integrity hash and decision metadata."""

    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")

    if not isinstance(description, str) or not description.strip():
        raise ValueError("description must be a non-empty string")

    latest_logs = get_audit_logs(limit=1)
    previous_hash = latest_logs[0].entry_hash if latest_logs else None

    created_at = datetime.now(timezone.utc)
    event_type = event_type.strip()
    description = description.strip()

    entry_hash = calculate_entry_hash(
        user_id=user_id,
        event_type=event_type,
        description=description,
        created_at=created_at,
        previous_hash=previous_hash,
    )

    log = AuditLog(
        user_id=user_id,
        conversation_id=conversation_id,
        request_ref=request_ref,
        event_type=event_type,
        description=description,
        reuse_detected=bool(reuse_detected),
        matched_record_id=matched_record_id,
        original_purpose=original_purpose,
        requested_purpose=requested_purpose,
        decision=decision,
        decision_reason=decision_reason,
        sent_to_provider=bool(sent_to_provider),
        created_at=created_at,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )

    from app import db

    db.session.add(log)
    db.session.commit()

    return log


def fetch_recent_events(limit=100, user_id=None):
    """Fetch recent audit events."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    return get_audit_logs(limit=limit, user_id=user_id)
