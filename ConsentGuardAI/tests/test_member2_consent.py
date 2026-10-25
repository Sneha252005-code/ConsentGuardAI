
"""Tests for purpose-specific consent management."""

import pytest

from consent.consent_repository import ConsentRepository
from consent.consent_service import ConsentService


@pytest.fixture
def service():
    return ConsentService(ConsentRepository())


def test_grant_consent_creates_record(service):
    record = service.grant_consent(
        user_id="user-1",
        purpose="customer_support",
        data_categories=["profile", "email"],
    )

    assert record.user_id == "user-1"
    assert record.purpose == "customer_support"
    assert set(record.data_categories) == {"profile", "email"}
    assert record.granted is True
    assert record.withdrawn_at is None


def test_consent_requires_matching_purpose_and_category(service):
    service.grant_consent(
        user_id="user-1",
        purpose="customer_support",
        data_categories=["profile"],
    )

    assert service.has_consent("user-1", "customer_support", "profile")
    assert not service.has_consent("user-1", "marketing", "profile")
    assert not service.has_consent("user-1", "customer_support", "location")


def test_withdrawal_blocks_future_consent_checks(service):
    record = service.grant_consent(
        user_id="user-1",
        purpose="customer_support",
        data_categories=["profile"],
    )

    service.withdraw_consent(record.consent_id)

    assert not service.has_consent("user-1", "customer_support", "profile")


def test_repeated_withdrawal_is_safe(service):
    record = service.grant_consent(
        user_id="user-1",
        purpose="customer_support",
        data_categories=["profile"],
    )

    service.withdraw_consent(record.consent_id)
    withdrawn_again = service.withdraw_consent(record.consent_id)

    assert withdrawn_again.granted is False
    assert withdrawn_again.withdrawn_at is not None


def test_unknown_consent_withdrawal_raises_error(service):
    with pytest.raises(KeyError):
        service.withdraw_consent("does-not-exist")
