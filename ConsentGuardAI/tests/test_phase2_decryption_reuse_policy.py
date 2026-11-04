"""Phase 2 tests: Trusted decryption, reuse detection, purpose rules, and ALLOW/WARN/BLOCK decisions."""

import pytest

from security.encryption import encrypt_data
from policy_engine.reuse_detector import DataReuseDetector, ReuseMatch
from policy_engine.purpose_engine import PurposeEngine
from policy_engine.policy_rules import PolicyRules
from policy_engine.authorization import AuthorizationService, AuthorizationDecision
from policy_engine.decision_explanations import DecisionExplainer
from consent.consent_repository import ConsentRepository
from consent.consent_service import ConsentService


class MockRecord:
    """Mock record for testing encrypted and plaintext storage."""

    def __init__(
        self,
        id: int,
        content: str,
        original_purpose: str,
        encrypted: bool = True,
        corrupt: bool = False,
        classification: str = "POSCO Confidential",
    ):
        self.id = id
        self.original_purpose = original_purpose
        self.data_classification = classification
        if encrypted:
            if corrupt:
                self.data_encrypted = b"gAAAAAB_corrupt_ciphertext_that_cannot_decrypt"
            else:
                self.data_encrypted = encrypt_data(content).encode("utf-8")
        else:
            self.data_encrypted = None
            self.content = content


@pytest.fixture
def detector():
    return DataReuseDetector()


@pytest.fixture
def policy_rules():
    return PolicyRules(PurposeEngine())


@pytest.fixture
def auth_service(policy_rules, detector):
    repo = ConsentRepository()
    service = ConsentService(repo)
    return AuthorizationService(service, policy_rules=policy_rules, reuse_detector=detector)


def test_trusted_decryption_detects_exact_reuse(detector):
    """Test that encrypted records are decrypted through trusted layer and exact reuse is caught."""
    confidential_text = (
        "During the internal inquiry regarding complaint #402, the committee "
        "reviewed the statement submitted by the supervisor."
    )
    record = MockRecord(
        id=101,
        content=confidential_text,
        original_purpose="HR Investigation Summary",
        encrypted=True,
    )

    prompt = f"Please analyze this text: {confidential_text}"
    match = detector.detect_in_records(prompt, [record])

    assert match.detected is True
    assert match.record_id == 101
    assert match.original_purpose == "HR Investigation Summary"
    assert match.match_type == "exact"
    assert match.decryption_failed is False


def test_trusted_decryption_detects_partial_clause_reuse(detector):
    """Test that partial sentences or confidential clauses from encrypted records are detected."""
    confidential_text = (
        "POSCO Internal Committee Finding: The complainant alleged inappropriate conduct "
        "during the quarterly evaluation meeting on March 12th."
    )
    record = MockRecord(
        id=102,
        content=confidential_text,
        original_purpose="POSCO Inquiry Record",
        encrypted=True,
    )

    # Prompt reuses only the confidential sentence
    prompt = "The complainant alleged inappropriate conduct during the quarterly evaluation meeting on March 12th."
    match = detector.detect_in_records(prompt, [record])

    assert match.detected is True
    assert match.record_id == 102
    assert match.match_type in ("exact", "partial")


def test_decryption_failure_never_silently_skipped(detector, policy_rules):
    """Security rule: When decryption fails, fail closed (BLOCK) rather than silently ignoring."""
    corrupt_record = MockRecord(
        id=999,
        content="Sensitive text",
        original_purpose="Secret HR Review",
        encrypted=True,
        corrupt=True,
    )

    match = detector.detect_in_records("Any innocent user prompt", [corrupt_record])

    assert match.detected is True
    assert match.decryption_failed is True

    decision = policy_rules.evaluate_purpose_reuse(
        reuse_match=match,
        requested_purpose="General summary",
    )
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert "cannot safely complete" in decision.reason or "failed" in decision.reason


def test_purpose_rules_same_purpose_allows(policy_rules):
    """Objective 4: Reusing tracked data for the same original purpose produces ALLOW."""
    reuse = ReuseMatch(
        detected=True,
        record_id=1,
        original_purpose="HR Investigation Summary",
        match_type="exact",
    )

    decision = policy_rules.evaluate_purpose_reuse(
        reuse_match=reuse,
        requested_purpose="HR Investigation Summary",
    )

    assert decision.allowed is True
    assert decision.decision == "ALLOW"
    assert "Data reuse authorized" in decision.reason


def test_purpose_rules_different_purpose_warns(policy_rules):
    """Objective 4: Reusing tracked data for different review-requiring purpose produces WARN."""
    reuse = ReuseMatch(
        detected=True,
        record_id=1,
        original_purpose="HR Investigation Summary",
        match_type="partial",
    )

    decision = policy_rules.evaluate_purpose_reuse(
        reuse_match=reuse,
        requested_purpose="Internal Legal Compliance Audit",
    )

    assert decision.allowed is False
    assert decision.decision == "WARN"
    assert decision.requires_review is True
    assert "Restricted data held" in decision.reason


def test_purpose_rules_prohibited_reuse_blocks(policy_rules):
    """Objective 4: Reusing confidential HR/POSCO data for external marketing or public memo produces BLOCK."""
    reuse = ReuseMatch(
        detected=True,
        record_id=1,
        original_purpose="POSCO Confidential Inquiry",
        match_type="exact",
    )

    # Attempting to use for marketing
    decision_mkt = policy_rules.evaluate_purpose_reuse(
        reuse_match=reuse,
        requested_purpose="External Marketing Campaign",
    )
    assert decision_mkt.allowed is False
    assert decision_mkt.decision == "BLOCK"
    assert "strictly prohibits" in decision_mkt.reason

    # Attempting to use for public announcement
    decision_pub = policy_rules.evaluate_purpose_reuse(
        reuse_match=reuse,
        requested_purpose="Public Announcement Memo",
    )
    assert decision_pub.allowed is False
    assert decision_pub.decision == "BLOCK"


def test_missing_original_purpose_blocks(policy_rules):
    """Missing original purpose must fail closed with BLOCK."""
    reuse = ReuseMatch(
        detected=True,
        record_id=2,
        original_purpose=None,
        match_type="exact",
    )

    decision = policy_rules.evaluate_purpose_reuse(
        reuse_match=reuse,
        requested_purpose="HR Review",
    )
    assert decision.allowed is False
    assert decision.decision == "BLOCK"
    assert "missing original purpose" in decision.reason


def test_no_reuse_detected_allows(policy_rules):
    """Clean prompt with no previously stored data produces ALLOW."""
    reuse = ReuseMatch(detected=False)

    decision = policy_rules.evaluate_purpose_reuse(
        reuse_match=reuse,
        requested_purpose="General Writing Assistance",
    )
    assert decision.allowed is True
    assert decision.decision == "ALLOW"


def test_decision_explainer_formats_allow_warn_block():
    """Verify DecisionExplainer formats all three decision types clearly."""
    explainer = DecisionExplainer()

    # ALLOW
    dec_allow = AuthorizationDecision(
        allowed=True,
        decision="ALLOW",
        user_id="user-1",
        purpose="HR Investigation Summary",
        data_category="HR",
        reason="Purpose matches original record.",
    )
    exp_allow = explainer.explain(dec_allow)
    assert exp_allow.decision == "ALLOW"
    assert "ALLOW" in exp_allow.summary

    # WARN
    dec_warn = AuthorizationDecision(
        allowed=False,
        decision="WARN",
        user_id="user-1",
        purpose="Compliance Audit",
        data_category="HR",
        reason="Potential purpose conflict.",
        requires_review=True,
    )
    exp_warn = explainer.explain(dec_warn)
    assert exp_warn.decision == "WARN"
    assert exp_warn.requires_review is True
    assert "WARN" in exp_warn.summary

    # BLOCK
    dec_block = AuthorizationDecision(
        allowed=False,
        decision="BLOCK",
        user_id="user-1",
        purpose="Marketing",
        data_category="HR",
        reason="Strictly prohibited by policy.",
    )
    exp_block = explainer.explain(dec_block)
    assert exp_block.decision == "BLOCK"
    assert exp_block.allowed is False
    assert "BLOCK" in exp_block.summary
