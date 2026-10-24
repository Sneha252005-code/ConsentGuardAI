
"""Database access helpers for ConsentGuardAI consent records."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from app import db
from database.models import ConsentModel


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

        if (
            not isinstance(data_categories, (list, tuple))
            or not data_categories
        ):
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
