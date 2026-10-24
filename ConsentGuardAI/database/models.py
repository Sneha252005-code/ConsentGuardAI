
"""Database models for ConsentGuardAI."""

from datetime import datetime, timezone

from app import db


class ProtectedRecord(db.Model):
    """Stores a user's protected data record and its original purpose."""

    __tablename__ = "protected_records"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    data_encrypted = db.Column(db.LargeBinary, nullable=False)
    original_purpose = db.Column(db.String(500), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<ProtectedRecord id={self.id} title={self.title!r}>"


class AuditLog(db.Model):
    """Stores security and authorization events."""

    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=True, index=True)
    event_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(1000), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    previous_hash = db.Column(db.String(64), nullable=True)
    entry_hash = db.Column(db.String(64), nullable=True)

    def __repr__(self):
        return f"<AuditLog id={self.id} event_type={self.event_type!r}>"
