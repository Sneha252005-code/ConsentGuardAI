"""Integrity verification for ConsentGuardAI audit logs."""

from datetime import timezone
import hashlib
import json

from database.models import AuditLog


def calculate_entry_hash(
    user_id,
    event_type,
    description,
    created_at,
    previous_hash=None,
):
    """Calculate a SHA-256 hash for an audit entry."""
    # Normalize created_at so both timezone-aware and SQLite naive UTC datetimes serialize consistently.
    if hasattr(created_at, "replace") and hasattr(created_at, "tzinfo"):
        if created_at.tzinfo is None:
            created_at_normalized = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at_normalized = created_at.astimezone(timezone.utc)
        created_str = created_at_normalized.isoformat()
    elif hasattr(created_at, "isoformat"):
        created_str = created_at.isoformat()
    else:
        created_str = str(created_at)

    payload = {
        "user_id": user_id,
        "event_type": event_type,
        "description": description,
        "created_at": created_str,
        "previous_hash": previous_hash,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def verify_audit_log(log):
    """Check whether a log entry matches its stored hash."""
    if not log.entry_hash:
        return False

    expected_hash = calculate_entry_hash(
        user_id=log.user_id,
        event_type=log.event_type,
        description=log.description,
        created_at=log.created_at,
        previous_hash=log.previous_hash,
    )

    return expected_hash == log.entry_hash


def verify_audit_chain(logs):
    """Verify hashes and links in chronological order across the global audit trail."""
    if not logs:
        return True

    sorted_logs = sorted(logs, key=lambda item: (item.id or 0, item.created_at))

    # Verify the first entry's cryptographic hash
    first_log = sorted_logs[0]
    if not verify_audit_log(first_log):
        return False

    previous_hash = first_log.entry_hash

    for log in sorted_logs[1:]:
        if log.previous_hash != previous_hash:
            return False

        if not verify_audit_log(log):
            return False

        previous_hash = log.entry_hash

    return True
