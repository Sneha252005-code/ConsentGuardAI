
from flask import Blueprint, jsonify, request, session

from app.middleware.rate_limit import (
    login_rate_limit,
    register_rate_limit,
)
from security.authentication import hash_password, verify_password
from security.validation import validate_email, validate_password

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

# Temporary storage for testing only.
# Replace with database storage before production.
_users = {}


@auth_bp.route("/register", methods=["POST"])
@register_rate_limit
def register():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "JSON object required."}), 400

    try:
        email = validate_email(data.get("email"))
        password = validate_password(data.get("password"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    if email in _users:
        return jsonify({"error": "Account already exists."}), 409

    _users[email] = {
        "password_hash": hash_password(password)
    }

    return jsonify({"message": "Registration successful."}), 201


@auth_bp.route("/login", methods=["POST"])
@login_rate_limit
def login():
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

    user = _users.get(email)

    if not user or not verify_password(user["password_hash"], password):
        return jsonify({"error": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = email

    return jsonify({"message": "Login successful."}), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logout successful."}), 200
