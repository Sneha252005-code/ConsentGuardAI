
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
