
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Optional
from uuid import uuid4


@dataclass
class ConsentRecord:
    """Represents a user's permission to use data for a specific purpose."""

    user_id: str
    purpose: str
    data_categories: tuple[str, ...]
    consent_id: str = field(default_factory=lambda: str(uuid4()))
    granted: bool = True
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    withdrawn_at: Optional[datetime] = None
    version: int = 1


class ConsentRepository:
    """Thread-safe in-memory repository for consent records.

    Note: records are lost when the application restarts. This implementation
    is suitable for development and tests; production should use the project's
    database layer.
    """

    def __init__(self) -> None:
        self._records: dict[str, ConsentRecord] = {}
        self._lock = RLock()

    @staticmethod
    def _validate_text(value: str, field_name: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name} must be a non-empty string.")
        return value.strip()

    def create(
        self,
        user_id: str,
        purpose: str,
        data_categories: list[str] | tuple[str, ...],
    ) -> ConsentRecord:
        user_id = self._validate_text(user_id, "user_id")
        purpose = self._validate_text(purpose, "purpose")

        if isinstance(data_categories, str) or not data_categories:
            raise ValueError("data_categories must contain at least one category.")

        categories = tuple(
            dict.fromkeys(
                self._validate_text(category, "data category")
                for category in data_categories
            )
        )
        if not categories:
            raise ValueError("At least one data category is required.")

        record = ConsentRecord(
            user_id=user_id,
            purpose=purpose,
            data_categories=categories,
        )
        with self._lock:
            self._records[record.consent_id] = record
        return record

    def get(self, consent_id: str) -> Optional[ConsentRecord]:
        consent_id = self._validate_text(consent_id, "consent_id")
        with self._lock:
            return self._records.get(consent_id)

    def list_for_user(self, user_id: str) -> list[ConsentRecord]:
        user_id = self._validate_text(user_id, "user_id")
        with self._lock:
            return [
                record
                for record in self._records.values()
                if record.user_id == user_id
            ]

    def find_active(
        self,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> Optional[ConsentRecord]:
        """Return an active consent matching user, purpose, and data category."""
        user_id = self._validate_text(user_id, "user_id")
        purpose = self._validate_text(purpose, "purpose")
        data_category = self._validate_text(data_category, "data_category")

        with self._lock:
            matches = [
                record
                for record in self._records.values()
                if record.user_id == user_id
                and record.purpose == purpose
                and data_category in record.data_categories
                and record.granted
                and record.withdrawn_at is None
            ]
            if not matches:
                return None
            return max(matches, key=lambda record: record.updated_at)

    def withdraw(self, consent_id: str) -> ConsentRecord:
        """Withdraw consent; repeated withdrawal is safe and idempotent."""
        consent_id = self._validate_text(consent_id, "consent_id")

        with self._lock:
            record = self._records.get(consent_id)
            if record is None:
                raise KeyError(f"Consent record not found: {consent_id}")

            if record.granted or record.withdrawn_at is None:
                now = datetime.now(timezone.utc)
                record.granted = False
                record.withdrawn_at = record.withdrawn_at or now
                record.updated_at = now
                record.version += 1

            return record

    def clear(self) -> None:
        """Clear all records. Intended for isolated tests only."""
        with self._lock:
            self._records.clear()
