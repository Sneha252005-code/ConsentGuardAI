
"""Human-readable explanations for authorization decisions."""

from dataclasses import dataclass

from policy_engine.authorization import AuthorizationDecision


@dataclass(frozen=True)
class DecisionExplanation:
    allowed: bool
    summary: str
    details: str
    consent_id: str | None = None


class DecisionExplainer:
    """Convert authorization results into clear, consistent explanations."""

    def explain(
        self,
        decision: AuthorizationDecision,
    ) -> DecisionExplanation:
        """Explain why a request was allowed or denied."""

        if decision.allowed:
            return DecisionExplanation(
                allowed=True,
                summary="Data access authorized.",
                details=(
                    f"{decision.reason} "
                    f"Purpose: {decision.purpose}. "
                    f"Data category: {decision.data_category}."
                ),
                consent_id=decision.consent_id,
            )

        return DecisionExplanation(
            allowed=False,
            summary="Data access denied.",
            details=(
                f"{decision.reason} "
                "No protected data should be released for this request."
            ),
            consent_id=None,
        )
