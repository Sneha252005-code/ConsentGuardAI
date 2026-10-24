
"""Authorization service for purpose-based data access."""

from dataclasses import dataclass

from consent.consent_service import ConsentService
from policy_engine.policy_rules import PolicyRules


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    user_id: str
    purpose: str
    data_category: str
    reason: str
    consent_id: str | None = None


class AuthorizationService:
    """Authorize data use only when matching active consent exists."""

    def __init__(
        self,
        consent_service: ConsentService,
        policy_rules: PolicyRules | None = None,
    ) -> None:
        self.consent_service = consent_service
        self.policy_rules = policy_rules or PolicyRules()

    def authorize(
        self,
        *,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> AuthorizationDecision:
        """Check consent and purpose before allowing data use."""

        if not all(
            isinstance(value, str) and value.strip()
            for value in (user_id, purpose, data_category)
        ):
            return AuthorizationDecision(
                False,
                user_id if isinstance(user_id, str) else "",
                purpose if isinstance(purpose, str) else "",
                data_category if isinstance(data_category, str) else "",
                "Missing or invalid authorization details; access denied.",
            )

        record = self.consent_service.repository.find_active(
            user_id=user_id,
            purpose=purpose,
            data_category=data_category,
        )

        if record is None:
            return AuthorizationDecision(
                False,
                user_id,
                purpose,
                data_category,
                "No matching active consent; access denied.",
            )

        result = self.policy_rules.evaluate(
            consent_active=record.granted and record.withdrawn_at is None,
            requested_purpose=purpose,
            consented_purpose=record.purpose,
            data_category_allowed=data_category in record.data_categories,
        )

        return AuthorizationDecision(
            allowed=result.allowed,
            user_id=user_id,
            purpose=purpose,
            data_category=data_category,
            reason=result.reason,
            consent_id=record.consent_id if result.allowed else None,
        )
