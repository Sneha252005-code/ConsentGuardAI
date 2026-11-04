"""Authorization policy rules for ConsentGuardAI (Objective 4)."""

from dataclasses import dataclass
from typing import Optional, Set

from policy_engine.purpose_engine import PurposeEngine
from policy_engine.reuse_detector import ReuseMatch


@dataclass(frozen=True)
class PolicyDecision:
    """Explicit, testable policy decision with ALLOW, WARN, or BLOCK."""

    allowed: bool
    decision: str  # "ALLOW", "WARN", "BLOCK"
    reason: str
    requires_review: bool = False
    original_purpose: Optional[str] = None
    requested_purpose: Optional[str] = None
    matched_record_id: Optional[int] = None
    reuse_detected: bool = False


class PolicyRules:
    """Evaluate purpose compatibility and determine Allow / Warn / Block decisions."""

    # Prohibited secondary uses for confidential or sensitive HR/POSCO records
    STRICTLY_PROHIBITED_KEYWORDS: Set[str] = {
        "marketing",
        "public",
        "social media",
        "advertisement",
        "commercial",
        "press release",
        "broadcast",
        "campaign",
        "external memo",
        "external announcement",
        "external publication",
        "blog",
    }

    # Review-required keywords (triggers WARN)
    REVIEW_REQUIRED_KEYWORDS: Set[str] = {
        "training",
        "analytics",
        "audit",
        "benchmark",
        "secondary research",
        "compliance check",
        "evaluation",
    }

    def __init__(self, purpose_engine: Optional[PurposeEngine] = None) -> None:
        self.purpose_engine = purpose_engine or PurposeEngine()

    def evaluate(
        self,
        *,
        consent_active: bool,
        requested_purpose: str,
        consented_purpose: str,
        data_category_allowed: bool,
    ) -> PolicyDecision:
        """Evaluate consent and purpose requirements before data use (Legacy/Category check)."""

        if not consent_active:
            return PolicyDecision(
                allowed=False,
                decision="BLOCK",
                reason="No active consent; access denied.",
                requested_purpose=requested_purpose,
            )

        if not data_category_allowed:
            return PolicyDecision(
                allowed=False,
                decision="BLOCK",
                reason="Data category is not covered by consent.",
                requested_purpose=requested_purpose,
            )

        purpose_check = self.purpose_engine.check_purpose(
            requested_purpose=requested_purpose,
            consented_purpose=consented_purpose,
        )

        if not purpose_check.allowed:
            return PolicyDecision(
                allowed=False,
                decision="BLOCK",
                reason=purpose_check.reason,
                requested_purpose=requested_purpose,
                original_purpose=consented_purpose,
            )

        return PolicyDecision(
            allowed=True,
            decision="ALLOW",
            reason="Active consent, permitted data category, and purpose match.",
            requested_purpose=requested_purpose,
            original_purpose=consented_purpose,
        )

    def evaluate_purpose_reuse(
        self,
        *,
        reuse_match: ReuseMatch,
        requested_purpose: str,
        consent_active: bool = True,
    ) -> PolicyDecision:
        """Compare original purpose with new purpose to generate ALLOW / WARN / BLOCK decision.

        Implements Objective 4:
        - ALLOW: Policy permits requested use (e.g. same original purpose or new request).
        - WARN: Potential purpose conflict / review required. Restricted data withheld.
        - BLOCK: Request violates policy, unauthorized extraction, or missing purpose.
        """
        # 1. Handle reuse detection / decryption failures (Fail-closed)
        if reuse_match.decryption_failed:
            return PolicyDecision(
                allowed=False,
                decision="BLOCK",
                reason=reuse_match.reason,
                matched_record_id=reuse_match.record_id,
                reuse_detected=True,
                requested_purpose=requested_purpose,
            )

        # 2. Case A: No previously stored data reuse detected
        if not reuse_match.detected:
            if not requested_purpose or not requested_purpose.strip():
                return PolicyDecision(
                    allowed=False,
                    decision="BLOCK",
                    reason="Requested purpose is missing or invalid; access denied.",
                    reuse_detected=False,
                )

            if not consent_active:
                return PolicyDecision(
                    allowed=False,
                    decision="BLOCK",
                    reason="No active consent for requested purpose; access denied.",
                    reuse_detected=False,
                    requested_purpose=requested_purpose,
                )

            return PolicyDecision(
                allowed=True,
                decision="ALLOW",
                reason="No previously stored data detected. Access granted for requested purpose.",
                reuse_detected=False,
                requested_purpose=requested_purpose,
            )

        # 3. Case B: Data reuse detected — enforce purpose comparison
        orig_purpose = (reuse_match.original_purpose or "").strip()
        req_purpose = (requested_purpose or "").strip()

        # Missing original purpose check
        if not orig_purpose:
            return PolicyDecision(
                allowed=False,
                decision="BLOCK",
                reason="Stored record is missing original purpose information; authorization cannot be established.",
                matched_record_id=reuse_match.record_id,
                reuse_detected=True,
                requested_purpose=req_purpose,
            )

        # Missing requested purpose check
        if not req_purpose:
            return PolicyDecision(
                allowed=False,
                decision="BLOCK",
                reason="New request is missing a declared purpose; authorization cannot be established.",
                matched_record_id=reuse_match.record_id,
                reuse_detected=True,
                original_purpose=orig_purpose,
            )

        orig_norm = orig_purpose.casefold()
        req_norm = req_purpose.casefold()

        # Rule 1: Prohibited Secondary Purpose
        # If confidential record (e.g. POSCO HR) is attempted to be reused for prohibited purposes
        for prohibited in self.STRICTLY_PROHIBITED_KEYWORDS:
            if prohibited in req_norm:
                return PolicyDecision(
                    allowed=False,
                    decision="BLOCK",
                    reason=(
                        f"Policy strictly prohibits reusing confidential data "
                        f"(original purpose: '{orig_purpose}') for '{req_purpose}'."
                    ),
                    matched_record_id=reuse_match.record_id,
                    reuse_detected=True,
                    original_purpose=orig_purpose,
                    requested_purpose=req_purpose,
                )

        # Rule 2: Same Authorized Purpose -> ALLOW
        purpose_check = self.purpose_engine.check_purpose(req_purpose, orig_purpose)
        if purpose_check.allowed or req_norm == orig_norm:
            return PolicyDecision(
                allowed=True,
                decision="ALLOW",
                reason=(
                    f"Data reuse authorized: requested purpose matches the "
                    f"original recorded purpose ('{orig_purpose}')."
                ),
                matched_record_id=reuse_match.record_id,
                reuse_detected=True,
                original_purpose=orig_purpose,
                requested_purpose=req_purpose,
            )

        # Rule 3: Purpose Conflict / Review Required -> WARN
        # When purpose differs from original purpose, do not send restricted data while review is pending
        return PolicyDecision(
            allowed=False,
            decision="WARN",
            requires_review=True,
            reason=(
                f"Potential purpose conflict: data was originally submitted for '{orig_purpose}', "
                f"but this request is for '{req_purpose}'. Restricted data held pending explicit review."
            ),
            matched_record_id=reuse_match.record_id,
            reuse_detected=True,
            original_purpose=orig_purpose,
            requested_purpose=req_purpose,
        )
