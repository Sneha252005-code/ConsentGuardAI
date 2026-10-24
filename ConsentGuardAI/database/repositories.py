
"""Database repository functions for ConsentGuardAI."""

from app import db
from database.models import ProtectedRecord, AuditLog


def create_protected_record(
    user_id,
    title,
    data_encrypted,
    original_purpose,
):
    """Create and save a protected data record."""
    record = ProtectedRecord(
        user_id=user_id,
        title=title,
        data_encrypted=data_encrypted,
        original_purpose=original_purpose,
    )
    db.session.add(record)
    db.session.commit()
    return record


def get_protected_record(record_id):
    """Retrieve a protected record by its ID."""
    return db.session.get(ProtectedRecord, record_id)


def get_user_protected_records(user_id):
    """Retrieve all protected records belonging to a user."""
    return (
        ProtectedRecord.query
        .filter_by(user_id=user_id)
        .order_by(ProtectedRecord.created_at.desc())
        .all()
    )


def delete_protected_record(record_id):
    """Delete a protected record by its ID."""
    record = get_protected_record(record_id)

    if record is None:
        return False

    db.session.delete(record)
    db.session.commit()
    return True


def create_audit_log(
    event_type,
    description,
    user_id=None,
    previous_hash=None,
    entry_hash=None,
):
    """Create and save an audit log entry."""
    log = AuditLog(
        user_id=user_id,
        event_type=event_type,
        description=description,
        previous_hash=previous_hash,
        entry_hash=entry_hash,
    )
    db.session.add(log)
    db.session.commit()
    return log


def get_audit_logs(limit=100):
    """Retrieve recent audit logs."""
    return (
        AuditLog.query
        .order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
