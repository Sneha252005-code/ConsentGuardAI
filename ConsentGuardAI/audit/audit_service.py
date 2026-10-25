
"""Audit logging service for ConsentGuardAI."""

from database.models import AuditLog
from database.repositories import create_audit_log, get_audit_logs
from audit.integrity import calculate_entry_hash


def record_event(
    event_type,
    description,
    user_id=None,
):
    """Record a security or authorization event with an integrity hash."""

    if not isinstance(event_type, str) or not event_type.strip():
        raise ValueError("event_type must be a non-empty string")

    if not isinstance(description, str) or not description.strip():
        raise ValueError("description must be a non-empty string")

    # Get the most recent audit entry to link the hash chain.
    latest_logs = get_audit_logs(limit=1)
    previous_hash = latest_logs[0].entry_hash if latest_logs else None

    # Use the same timestamp for hashing and storing the event.
    from datetime import datetime, timezone

    created_at = datetime.now(timezone.utc)

    entry_hash = calculate_entry_hash(
        user_id=user_id,
        event_type=event_type.strip(),
        description=description.strip(),
        created_at=created_at,
        previous_hash=previous_hash,
    )

    log = AuditLog(
        user_id=user_id,
        event_type=event_type.strip(),
        description=description.strip(),
        created_at=created_at,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )

    from app import db

    db.session.add(log)
    db.session.commit()

    return log


def fetch_recent_events(limit=100):
    """Fetch recent audit events."""

    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError("limit must be a positive integer")

    return get_audit_logs(limit=limit)
