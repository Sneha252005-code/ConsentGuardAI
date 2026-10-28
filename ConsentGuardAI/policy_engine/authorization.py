
"""Authorization service for purpose-based data access."""

from dataclasses import dataclass

from consent.consent_service import ConsentService
from policy_engine.policy_rules import PolicyRules


@dataclass(frozen=True)
class AuthorizationDecision:
    """Result of an authorization check."""

    allowed: bool
    user_id: str
    purpose: str
    data_category: str
    reason: str
    consent_id: str | None = None


class AuthorizationService:
    """Authorize data access based on active consent and purpose."""

    def __init__(self, consent_service: ConsentService):
        self.consent_service = consent_service
        self.policy_rules = PolicyRules()

    def authorize(
        self,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> AuthorizationDecision:
        """Check whether the requested data use is authorized."""

        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string.")

        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("purpose must be a non-empty string.")

        if not isinstance(data_category, str) or not data_category.strip():
            raise ValueError("data_category must be a non-empty string.")

        try:
            allowed = self.consent_service.has_consent(
                user_id=user_id,
                purpose=purpose,
                data_category=data_category,
            )
        except Exception:
            return AuthorizationDecision(
                allowed=False,
                user_id=user_id,
                purpose=purpose,
                data_category=data_category,
                reason="Unable to verify consent.",
            )

        return AuthorizationDecision(
            allowed=allowed,
            user_id=user_id,
            purpose=purpose,
            data_category=data_category,
            reason=(
                "Authorization granted."
                if allowed
                else "No active consent matches this user, purpose, and data category."
            ),
        )