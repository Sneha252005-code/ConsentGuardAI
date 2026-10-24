
from __future__ import annotations

from typing import Optional

from consent.consent_repository import ConsentRecord, ConsentRepository


class ConsentService:
    """Business logic for managing purpose-specific user consent."""

    def __init__(self, repository: Optional[ConsentRepository] = None) -> None:
        self.repository = repository or ConsentRepository()

    def grant_consent(
        self,
        user_id: str,
        purpose: str,
        data_categories: list[str],
    ) -> ConsentRecord:
        """Record explicit consent for specific data categories and a purpose."""
        return self.repository.create(
            user_id=user_id,
            purpose=purpose,
            data_categories=data_categories,
        )

    def get_consent(self, consent_id: str) -> Optional[ConsentRecord]:
        """Retrieve a consent record by its ID."""
        return self.repository.get(consent_id)

    def get_user_consents(self, user_id: str) -> list[ConsentRecord]:
        """List all consent records belonging to a user."""
        return self.repository.list_for_user(user_id)

    def has_consent(
        self,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> bool:
        """Return True only when an active matching consent exists."""
        return (
            self.repository.find_active(
                user_id=user_id,
                purpose=purpose,
                data_category=data_category,
            )
            is not None
        )

    def withdraw_consent(self, consent_id: str) -> ConsentRecord:
        """Withdraw consent so future matching authorization requests fail."""
        return self.repository.withdraw(consent_id)
