

"""SQLAlchemy models for ConsentGuardAI."""

from datetime import datetime, timezone

from app import db


class ConsentModel(db.Model):
    """Persistent record of a user's purpose-specific consent."""

    __tablename__ = "consents"

    id = db.Column(db.String(36), primary_key=True)
    user_id = db.Column(db.String(255), nullable=False, index=True)
    purpose = db.Column(db.String(255), nullable=False, index=True)
    data_categories = db.Column(db.JSON, nullable=False)
    granted = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    withdrawn_at = db.Column(db.DateTime(timezone=True), nullable=True)
    version = db.Column(db.Integer, nullable=False, default=1)


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


class User(db.Model):
    """Stores registered user accounts."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<User id={self.id} email={self.email!r}>"
