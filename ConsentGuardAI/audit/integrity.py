
"""Integrity verification for ConsentGuardAI audit logs."""

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
    payload = {
        "user_id": user_id,
        "event_type": event_type,
        "description": description,
        "created_at": created_at.isoformat(),
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
    """Verify hashes and links in chronological order."""
    previous_hash = None

    for log in sorted(logs, key=lambda item: (item.created_at, item.id or 0)):
        if log.previous_hash != previous_hash:
            return False

        if not verify_audit_log(log):
            return False

        previous_hash = log.entry_hash

    return True
