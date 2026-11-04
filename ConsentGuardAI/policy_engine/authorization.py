"""Authorization service for purpose-based data access (Objective 4)."""

from dataclasses import dataclass
from typing import Optional, List

from consent.consent_service import ConsentService
from policy_engine.policy_rules import PolicyRules, PolicyDecision
from policy_engine.reuse_detector import DataReuseDetector, ReuseMatch


@dataclass(frozen=True)
class AuthorizationDecision:
    """Result of an authorization check."""

    allowed: bool
    user_id: str
    purpose: str
    data_category: str
    reason: str
    decision: str = "BLOCK"  # "ALLOW", "WARN", "BLOCK"
    consent_id: Optional[str] = None
    original_purpose: Optional[str] = None
    matched_record_id: Optional[int] = None
    reuse_detected: bool = False
    requires_review: bool = False


class AuthorizationService:
    """Authorize data access based on active consent, reuse detection, and purpose comparison."""

    def __init__(
        self,
        consent_service: ConsentService,
        policy_rules: Optional[PolicyRules] = None,
        reuse_detector: Optional[DataReuseDetector] = None,
    ):
        self.consent_service = consent_service
        self.policy_rules = policy_rules or PolicyRules()
        self.reuse_detector = reuse_detector or DataReuseDetector()

    def authorize(
        self,
        user_id: str,
        purpose: str,
        data_category: str,
    ) -> AuthorizationDecision:
        """Check whether the requested data use is authorized by active consent (Category check)."""

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
                decision="BLOCK",
                user_id=user_id,
                purpose=purpose,
                data_category=data_category,
                reason="Unable to verify consent.",
            )

        return AuthorizationDecision(
            allowed=allowed,
            decision="ALLOW" if allowed else "BLOCK",
            user_id=user_id,
            purpose=purpose,
            data_category=data_category,
            reason=(
                "Authorization granted."
                if allowed
                else "No active consent matches this user, purpose, and data category."
            ),
        )

    def authorize_prompt_request(
        self,
        *,
        user_id: str,
        prompt: str,
        purpose: str,
        data_category: str = "General",
        records: Optional[list] = None,
    ) -> AuthorizationDecision:
        """Perform comprehensive authorization: reuse detection, purpose comparison, and policy check.

        Implements Objectives 3 & 4:
        1. Detects reuse of stored protected records (with trusted decryption).
        2. Compares original purpose with requested purpose.
        3. Enforces ALLOW, WARN, or BLOCK policy outcomes.
        """
        if not isinstance(user_id, str) or not user_id.strip():
            raise ValueError("user_id must be a non-empty string.")

        if not isinstance(purpose, str) or not purpose.strip():
            raise ValueError("purpose must be a non-empty string.")

        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt must be a non-empty string.")

        user_records = records if records is not None else []

        # 1. Detect reuse in user's protected records
        try:
            reuse_match = self.reuse_detector.detect_in_records(
                prompt=prompt,
                records=user_records,
            )
        except Exception as err:
            return AuthorizationDecision(
                allowed=False,
                decision="BLOCK",
                user_id=user_id,
                purpose=purpose,
                data_category=data_category,
                reason=f"Protected-data reuse detection failed: {err}",
                reuse_detected=True,
            )

        # 2. Check general consent if needed
        consent_active = True
        try:
            if hasattr(self.consent_service, "has_consent"):
                # If a specific consent record exists for this category, check it
                user_consents = self.consent_service.get_user_consents(user_id)
                if user_consents:
                    consent_active = self.consent_service.has_consent(
                        user_id=user_id,
                        purpose=purpose,
                        data_category=data_category,
                    )
        except Exception:
            consent_active = True  # Proceed to purpose-based policy evaluation

        # 3. Evaluate purpose-based policy rules
        policy_decision = self.policy_rules.evaluate_purpose_reuse(
            reuse_match=reuse_match,
            requested_purpose=purpose,
            consent_active=consent_active,
        )

        return AuthorizationDecision(
            allowed=policy_decision.allowed,
            decision=policy_decision.decision,
            user_id=user_id,
            purpose=purpose,
            data_category=data_category,
            reason=policy_decision.reason,
            original_purpose=policy_decision.original_purpose,
            matched_record_id=policy_decision.matched_record_id,
            reuse_detected=policy_decision.reuse_detected,
            requires_review=policy_decision.requires_review,
        )
