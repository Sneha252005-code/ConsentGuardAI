
"""Database access helpers for ConsentGuardAI consent records."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from app import db
from database.models import ConsentModel


class ConsentDatabaseRepository:
    """Persist and retrieve consent records using SQLAlchemy."""

    def create(
        self,
        *,
        consent_id: str,
        user_id: str,
        purpose: str,
        data_categories: list[str],
    ) -> ConsentModel:
        record = ConsentModel(
            id=consent_id,
            user_id=user_id,
            purpose=purpose,
            data_categories=list(data_categories),
            granted=True,
            version=1,
        )
        db.session.add(record)
        db.session.commit()
        return record

    def get(self, consent_id: str) -> Optional[ConsentModel]:
        return db.session.get(ConsentModel, consent_id)

    def list_for_user(self, user_id: str) -> list[ConsentModel]:
        return ConsentModel.query.filter_by(user_id=user_id).all()

    def find_active(
        self,
        *,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> Optional[ConsentModel]:
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
        record = self.get(consent_id)
        if record is None:
            raise KeyError(f"Consent record not found: {consent_id}")

        if record.granted or record.withdrawn_at is None:
            now = datetime.now(timezone.utc)
            record.granted = False
            record.withdrawn_at = record.withdrawn_at or now
            record.updated_at = now
            record.version += 1
            db.session.commit()

        return record
