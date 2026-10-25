
"""Tests for persistent consent database storage."""

import pytest

from app import create_app, db
from database.models import ConsentModel
from database.repositories import ConsentDatabaseRepository


@pytest.fixture
def repository():
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite://"
    app.config["TESTING"] = True

    with app.app_context():
        db.drop_all()
        db.create_all()
        yield ConsentDatabaseRepository()
        db.session.remove()
        db.drop_all()


def test_create_and_retrieve_consent(repository):
    record = repository.create(
        consent_id="test-consent-1",
        user_id="test-user",
        purpose="customer_support",
        data_categories=["profile", "email"],
    )

    retrieved = repository.get(record.id)

    assert retrieved is not None
    assert retrieved.user_id == "test-user"
    assert retrieved.purpose == "customer_support"
    assert set(retrieved.data_categories) == {"profile", "email"}
    assert retrieved.granted is True


def test_find_active_requires_matching_purpose_and_category(repository):
    repository.create(
        consent_id="test-consent-2",
        user_id="test-user",
        purpose="customer_support",
        data_categories=["profile"],
    )

    assert repository.find_active(
        user_id="test-user",
        purpose="customer_support",
        data_category="profile",
    ) is not None

    assert repository.find_active(
        user_id="test-user",
        purpose="marketing",
        data_category="profile",
    ) is None


def test_withdrawal_prevents_active_lookup(repository):
    record = repository.create(
        consent_id="test-consent-3",
        user_id="test-user",
        purpose="customer_support",
        data_categories=["profile"],
    )

    repository.withdraw(record.id)

    assert repository.find_active(
        user_id="test-user",
        purpose="customer_support",
        data_category="profile",
    ) is None
