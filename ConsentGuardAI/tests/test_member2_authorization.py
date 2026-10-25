
import pytest

from consent.consent_repository import ConsentRepository
from consent.consent_service import ConsentService
from policy_engine.authorization import AuthorizationService


@pytest.fixture
def setup_authorization():
    service = ConsentService(ConsentRepository())
    service.grant_consent(
        user_id="user-1",
        purpose="customer_support",
        data_categories=["profile", "email"],
    )
    return service, AuthorizationService(service)


def test_matching_consent_allows_access(setup_authorization):
    _, auth = setup_authorization
    decision = auth.authorize(
        user_id="user-1",
        purpose="customer_support",
        data_category="profile",
    )
    assert decision.allowed is True


def test_wrong_purpose_denies_access(setup_authorization):
    _, auth = setup_authorization
    decision = auth.authorize(
        user_id="user-1",
        purpose="marketing",
        data_category="profile",
    )
    assert decision.allowed is False


def test_unconsented_category_denies_access(setup_authorization):
    _, auth = setup_authorization
    decision = auth.authorize(
        user_id="user-1",
        purpose="customer_support",
        data_category="location",
    )
    assert decision.allowed is False


def test_withdrawn_consent_denies_access(setup_authorization):
    service, auth = setup_authorization
    record = service.get_user_consents("user-1")[0]
    service.withdraw_consent(record.consent_id)

    decision = auth.authorize(
        user_id="user-1",
        purpose="customer_support",
        data_category="profile",
    )
    assert decision.allowed is False


def test_unknown_user_denied(setup_authorization):
    _, auth = setup_authorization
    decision = auth.authorize(
        user_id="unknown-user",
        purpose="customer_support",
        data_category="profile",
    )
    assert decision.allowed is False
