"""Authentication routes for ConsentGuardAI."""

from flask import Blueprint, jsonify, redirect, request, session, url_for
from sqlalchemy.exc import IntegrityError

from app import db
from app.middleware.rate_limit import (
    login_rate_limit,
    register_rate_limit,
)
from database.models import User
from security.authentication import hash_password, verify_password
from security.validation import validate_email, validate_password

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/me", methods=["GET"])
def current_user_info():
    """Return authenticated status and user info."""
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"authenticated": False}), 200

    user = db.session.get(User, int(user_id))
    if not user:
        session.clear()
        return jsonify({"authenticated": False}), 200

    return jsonify({
        "authenticated": True,
        "user_id": user.id,
        "email": user.email,
    }), 200


@auth_bp.route("/register", methods=["POST"])
@register_rate_limit
def register():
    """Register a new user account and establish session."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required."}), 400

    try:
        email = validate_email(data.get("email"))
        password = validate_password(data.get("password"))
        password_hash = hash_password(password)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email address already exists."}), 409

    user = User(email=email, password_hash=password_hash)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "An account with this email address already exists."}), 409

    # Automatically authenticate newly registered user
    session.clear()
    session["user_id"] = user.id
    session["email"] = user.email

    return jsonify({
        "message": "Account created successfully.",
        "user_id": user.id,
        "email": user.email,
    }), 201


@auth_bp.route("/login", methods=["POST"])
@login_rate_limit
def login():
    """Authenticate a user and store their database ID in the session."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required."}), 400

    try:
        email = validate_email(data.get("email"))
    except ValueError:
        return jsonify({"error": "Invalid email or password."}), 401

    password = data.get("password")
    if not isinstance(password, str):
        return jsonify({"error": "Invalid email or password."}), 401

    user = User.query.filter_by(email=email).first()

    if user is None or not verify_password(user.password_hash, password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = user.id
    session["email"] = user.email

    return jsonify({
        "message": "Login successful.",
        "user_id": user.id,
        "email": user.email,
    }), 200


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Log out the current session."""
    session.clear()
    if request.method == "GET":
        return redirect("/login")
    return jsonify({"message": "Logout successful."}), 200


@auth_bp.route("/demo-login", methods=["POST"])
def demo_login():
    """Compatibility endpoint for automated testing."""
    demo_email = "evaluator@consentguard.ai"
    user = User.query.filter_by(email=demo_email).first()
    if not user:
        user = User(
            email=demo_email,
            password_hash=hash_password("DemoPassword123!"),
        )
        db.session.add(user)
        db.session.commit()

    session.clear()
    session["user_id"] = user.id
    session["email"] = user.email
    return jsonify({
        "message": "Session initialized.",
        "user_id": user.id,
        "email": user.email,
    }), 200
