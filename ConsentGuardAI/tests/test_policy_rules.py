
"""Tests for purpose-based policy rules."""

from policy_engine.policy_rules import PolicyRules


def test_matching_active_consent_allows_access():
    rules = PolicyRules()

    decision = rules.evaluate(
        consent_active=True,
        requested_purpose="customer_support",
        consented_purpose="customer_support",
        data_category_allowed=True,
    )

    assert decision.allowed is True


def test_missing_consent_denies_access():
    rules = PolicyRules()

    decision = rules.evaluate(
        consent_active=False,
        requested_purpose="customer_support",
        consented_purpose="customer_support",
        data_category_allowed=True,
    )

    assert decision.allowed is False


def test_mismatched_purpose_denies_access():
    rules = PolicyRules()

    decision = rules.evaluate(
        consent_active=True,
        requested_purpose="marketing",
        consented_purpose="customer_support",
        data_category_allowed=True,
    )

    assert decision.allowed is False


def test_unapproved_data_category_denies_access():
    rules = PolicyRules()

    decision = rules.evaluate(
        consent_active=True,
        requested_purpose="customer_support",
        consented_purpose="customer_support",
        data_category_allowed=False,
    )

    assert decision.allowed is False
