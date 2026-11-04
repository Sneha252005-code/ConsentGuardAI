"""Human-readable explanations for authorization decisions (ALLOW / WARN / BLOCK)."""

from dataclasses import dataclass
from typing import Optional

from policy_engine.authorization import AuthorizationDecision


@dataclass(frozen=True)
class DecisionExplanation:
    allowed: bool
    decision: str  # "ALLOW", "WARN", "BLOCK"
    summary: str
    details: str
    consent_id: Optional[str] = None
    requires_review: bool = False


class DecisionExplainer:
    """Convert authorization results into clear, consistent explanations."""

    def explain(
        self,
        decision: AuthorizationDecision,
    ) -> DecisionExplanation:
        """Explain why a request was allowed, warned, or blocked."""
        decision_type = getattr(decision, "decision", "ALLOW" if decision.allowed else "BLOCK")

        if decision_type == "ALLOW":
            return DecisionExplanation(
                allowed=True,
                decision="ALLOW",
                summary="Request Authorized (ALLOW)",
                details=(
                    f"{decision.reason} "
                    f"Requested purpose: '{decision.purpose}'. "
                    "Prompt is approved for AI processing."
                ),
                consent_id=decision.consent_id,
                requires_review=False,
            )

        if decision_type == "WARN":
            return DecisionExplanation(
                allowed=False,
                decision="WARN",
                summary="Purpose Conflict Warning (WARN)",
                details=(
                    f"{decision.reason} "
                    "Restricted user data is held pending explicit review. "
                    "It has NOT been transmitted to the external AI provider."
                ),
                consent_id=decision.consent_id,
                requires_review=True,
            )

        # BLOCK
        return DecisionExplanation(
            allowed=False,
            decision="BLOCK",
            summary="Request Blocked by Policy (BLOCK)",
            details=(
                f"{decision.reason} "
                "The requested use violates policy or authorization cannot be established. "
                "Data has been blocked from reaching the external AI provider."
            ),
            consent_id=None,
            requires_review=False,
        )
