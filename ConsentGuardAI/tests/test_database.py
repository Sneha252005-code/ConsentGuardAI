
"""Tests for ConsentGuardAI database models, repositories, and audit integrity."""

from datetime import datetime, timezone

import pytest
from flask import Flask

from app import db
from app.config import Config
from database.models import ProtectedRecord, AuditLog
from database.repositories import (
    create_protected_record,
    get_protected_record,
    get_user_protected_records,
    create_audit_log,
    get_audit_logs,
)
from audit.integrity import (
    calculate_entry_hash,
    verify_audit_log,
)
from audit.audit_service import (
    record_event,
    fetch_recent_events,
)


@pytest.fixture
def app():
    """Create an isolated Flask app with an in-memory test database."""
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )

    db.init_app(app)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the Flask application."""
    return app.test_client()


def test_create_and_get_protected_record(app):
    """Test creating and retrieving a protected record."""
    with app.app_context():
        record = create_protected_record(
            user_id=1,
            title="Test image",
            data_encrypted=b"encrypted-test-data",
            original_purpose="Remove image background",
        )

        fetched = get_protected_record(record.id)

        assert fetched is not None
        assert fetched.id == record.id
        assert fetched.user_id == 1
        assert fetched.title == "Test image"
        assert fetched.original_purpose == "Remove image background"
        assert fetched.data_encrypted == b"encrypted-test-data"


def test_get_user_protected_records(app):
    """Test that records are filtered by user ID."""
    with app.app_context():
        create_protected_record(
            user_id=1,
            title="User one record",
            data_encrypted=b"encrypted-one",
            original_purpose="Image editing",
        )
        create_protected_record(
            user_id=2,
            title="User two record",
            data_encrypted=b"encrypted-two",
            original_purpose="Document summary",
        )

        records = get_user_protected_records(1)

        assert len(records) == 1
        assert records[0].user_id == 1
        assert records[0].title == "User one record"


def test_create_and_get_audit_log(app):
    """Test creating and retrieving an audit log."""
    with app.app_context():
        log = create_audit_log(
            event_type="AUTHORIZATION",
            description="Record access allowed",
            user_id=1,
        )

        logs = get_audit_logs(limit=10)

        assert log.id is not None
        assert log.event_type == "AUTHORIZATION"
        assert any(item.id == log.id for item in logs)


def test_models_have_expected_tables(app):
    """Test that the expected database tables exist."""
    with app.app_context():
        assert "protected_records" in db.metadata.tables
        assert "audit_logs" in db.metadata.tables
        assert db.session.query(ProtectedRecord).count() == 0
        assert db.session.query(AuditLog).count() == 0


def test_audit_entry_hash_is_consistent(app):
    """Test that identical audit data produces identical hashes."""
    with app.app_context():
        timestamp = datetime.now(timezone.utc)

        first_hash = calculate_entry_hash(
            user_id=1,
            event_type="RECORD_ACCESS",
            description="Access allowed",
            created_at=timestamp,
        )

        second_hash = calculate_entry_hash(
            user_id=1,
            event_type="RECORD_ACCESS",
            description="Access allowed",
            created_at=timestamp,
        )

        assert first_hash == second_hash
        assert len(first_hash) == 64


def test_audit_log_detects_modified_description(app):
    """Test that modifying an audit entry invalidates its hash."""
    with app.app_context():
        timestamp = datetime.now(timezone.utc)

        log = AuditLog(
            user_id=1,
            event_type="RECORD_ACCESS",
            description="Access allowed",
            created_at=timestamp,
        )

        log.entry_hash = calculate_entry_hash(
            user_id=log.user_id,
            event_type=log.event_type,
            description=log.description,
            created_at=log.created_at,
            previous_hash=log.previous_hash,
        )

        assert verify_audit_log(log) is True

        log.description = "Access denied"

        assert verify_audit_log(log) is False


def test_audit_service_records_event(app):
    """Test that the audit service records an event with an integrity hash."""
    with app.app_context():
        event = record_event(
            event_type="RECORD_CREATED",
            description="A protected record was created",
            user_id=1,
        )

        assert event.id is not None
        assert event.event_type == "RECORD_CREATED"
        assert event.description == "A protected record was created"
        assert event.user_id == 1
        assert event.entry_hash is not None
        assert len(event.entry_hash) == 64


def test_audit_service_rejects_invalid_limit(app):
    """Test that the audit service rejects invalid limits."""
    with app.app_context():
        with pytest.raises(ValueError):
            fetch_recent_events(limit=0)

        with pytest.raises(ValueError):
            fetch_recent_events(limit=-1)
