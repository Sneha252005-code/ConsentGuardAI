
from __future__ import annotations

from consent.consent_repository import ConsentRecord, ConsentRepository


class ConsentWithdrawalService:
    """Handles withdrawal of previously granted consent."""

    def __init__(self, repository: ConsentRepository) -> None:
        self.repository = repository

    def withdraw(self, consent_id: str) -> ConsentRecord:
        """Withdraw consent and return the updated record."""
        return self.repository.withdraw(consent_id)

    def is_withdrawn(self, consent_id: str) -> bool:
        """Return whether consent is missing or no longer active."""
        record = self.repository.get(consent_id)

        # Fail closed: a missing record cannot authorize data use.
        if record is None:
            return True

        return not record.granted or record.withdrawn_at is not None
