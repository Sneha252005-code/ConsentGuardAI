
from typing import Any, Callable


class AccessDeniedError(Exception):
    """Raised when access to protected data is denied."""


def enforce_access(
    consent_record: Any,
    requested_purpose: str,
    policy_checker: Callable[..., Any] | None = None,
) -> bool:
    """
    Enforce a consent-policy decision.
    Deny access if the policy checker is unavailable or returns an
    unrecognized decision.
    """
    if not isinstance(requested_purpose, str) or not requested_purpose.strip():
        return False

    if policy_checker is None:
        # Connect Member 2's policy engine when it is available.
        try:
            from policy_engine.consent_policy import evaluate_consent
            policy_checker = evaluate_consent
        except (ImportError, AttributeError):
            return False

    try:
        decision = policy_checker(consent_record, requested_purpose)
    except Exception:
        # Fail closed if the policy engine fails.
        return False

    # Support boolean decisions or an enum/string decision of "allow".
    if decision is True:
        return True

    decision_value = getattr(decision, "value", decision)
    return isinstance(decision_value, str) and decision_value.lower() == "allow"
