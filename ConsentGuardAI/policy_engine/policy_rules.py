
"""Authorization policy rules for ConsentGuardAI."""

from dataclasses import dataclass

from policy_engine.purpose_engine import PurposeEngine


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str


class PolicyRules:
    """Evaluate consent and purpose requirements before data use."""

    def __init__(self, purpose_engine: PurposeEngine | None = None) -> None:
        self.purpose_engine = purpose_engine or PurposeEngine()

    def evaluate(
        self,
        *,
        consent_active: bool,
        requested_purpose: str,
        consented_purpose: str,
        data_category_allowed: bool,
    ) -> PolicyDecision:
        """Deny by default unless all required checks pass."""

        if not consent_active:
            return PolicyDecision(
                allowed=False,
                reason="No active consent; access denied.",
            )

        if not data_category_allowed:
            return PolicyDecision(
                allowed=False,
                reason="Data category is not covered by consent.",
            )

        purpose_check = self.purpose_engine.check_purpose(
            requested_purpose=requested_purpose,
            consented_purpose=consented_purpose,
        )

        if not purpose_check.allowed:
            return PolicyDecision(
                allowed=False,
                reason=purpose_check.reason,
            )

        return PolicyDecision(
            allowed=True,
            reason="Active consent, permitted data category, and purpose match.",
        )
