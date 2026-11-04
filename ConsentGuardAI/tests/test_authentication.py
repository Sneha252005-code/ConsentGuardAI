import pytest
from flask import Flask

from app import db
from app.routes.auth_routes import auth_bp
from database.models import User
from security.authentication import (
    hash_password,
    verify_password,
    password_hash_needs_update,
)


# ==============================================================================
# Unit Tests for Argon2id Security Functions
# ==============================================================================

def test_password_is_hashed():
    password = "StrongPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(hashed, password)


def test_wrong_password_is_rejected():
    hashed = hash_password("StrongPassword123!")

    assert not verify_password(hashed, "WrongPassword123!")


def test_different_hashes_for_same_password():
    password = "StrongPassword123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(first_hash, password)
    assert verify_password(second_hash, password)


def test_short_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("short")


def test_non_string_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password(None)


def test_invalid_hash_returns_false():
    assert not verify_password("invalid-hash", "StrongPassword123!")


def test_rehash_check_handles_invalid_hash():
    assert not password_hash_needs_update("invalid-hash")


# ==============================================================================
# End-to-End Tests for Authentication & Session Routes
# ==============================================================================

@pytest.fixture
def auth_app():
    """Create isolated Flask app with in-memory SQLite for auth testing."""
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        SECRET_KEY="test-auth-session-key",
    )
    db.init_app(app)
    app.register_blueprint(auth_bp)

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def auth_client(auth_app):
    return auth_app.test_client()


def test_registration_flow_establishes_session(auth_client):
    """Registering a new account automatically creates session and authenticates user."""
    # 1. Register with valid 12+ character password
    resp = auth_client.post("/auth/register", json={
        "email": "newuser@enterprise.org",
        "password": "CompliantPassword2026!"
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["email"] == "newuser@enterprise.org"
    assert "user_id" in data

    # 2. Verify /auth/me returns authenticated status
    me_resp = auth_client.get("/auth/me")
    assert me_resp.status_code == 200
    me_data = me_resp.get_json()
    assert me_data["authenticated"] is True
    assert me_data["email"] == "newuser@enterprise.org"


def test_registration_rejects_short_password(auth_client):
    """Passwords shorter than 12 characters are rejected."""
    resp = auth_client.post("/auth/register", json={
        "email": "user@enterprise.org",
        "password": "short_pass"
    })
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data


def test_registration_rejects_duplicate_email(auth_client):
    """Duplicate email registration is rejected with 409 Conflict."""
    auth_client.post("/auth/register", json={
        "email": "existing@enterprise.org",
        "password": "CompliantPassword2026!"
    })
    resp = auth_client.post("/auth/register", json={
        "email": "existing@enterprise.org",
        "password": "AnotherCompliantPass2026!"
    })
    assert resp.status_code == 409


def test_login_and_logout_lifecycle(auth_client):
    """Complete login -> session check -> logout lifecycle."""
    # Register user
    auth_client.post("/auth/register", json={
        "email": "staff@enterprise.org",
        "password": "SecurePassword123!"
    })

    # Clear session by logging out
    auth_client.post("/auth/logout")

    # Confirm session is unauthenticated
    me_resp = auth_client.get("/auth/me")
    assert me_resp.get_json()["authenticated"] is False

    # Log in with valid credentials
    login_resp = auth_client.post("/auth/login", json={
        "email": "staff@enterprise.org",
        "password": "SecurePassword123!"
    })
    assert login_resp.status_code == 200
    assert login_resp.get_json()["email"] == "staff@enterprise.org"

    # Confirm authenticated state
    me_resp2 = auth_client.get("/auth/me")
    assert me_resp2.get_json()["authenticated"] is True
    assert me_resp2.get_json()["email"] == "staff@enterprise.org"

    # Logout via POST
    logout_resp = auth_client.post("/auth/logout")
    assert logout_resp.status_code == 200

    # Confirm session cleared
    me_resp3 = auth_client.get("/auth/me")
    assert me_resp3.get_json()["authenticated"] is False

    # Logout via GET redirects to login
    get_logout_resp = auth_client.get("/auth/logout")
    assert get_logout_resp.status_code == 302
    assert "/login" in get_logout_resp.headers["Location"]


def test_login_rejects_invalid_credentials(auth_client):
    """Bad password returns 401 Unauthorized."""
    auth_client.post("/auth/register", json={
        "email": "analyst@enterprise.org",
        "password": "CorrectPassword123!"
    })
    auth_client.post("/auth/logout")

    resp = auth_client.post("/auth/login", json={
        "email": "analyst@enterprise.org",
        "password": "WrongPassword999!"
    })
    assert resp.status_code == 401
    assert "error" in resp.get_json()
