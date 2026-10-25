"""Authentication routes for ConsentGuardAI."""

from flask import Blueprint, jsonify, request, session
from sqlalchemy.exc import IntegrityError

from app import db
from database.models import User
from security.authentication import hash_password, verify_password
from security.validation import validate_email, validate_password

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.route("/register", methods=["POST"])
def register():
    """Register a user in the database."""
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
        return jsonify({"error": "Account already exists."}), 409

    user = User(email=email, password_hash=password_hash)
    db.session.add(user)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify({"error": "Account already exists."}), 409

    return jsonify({"message": "Registration successful."}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Authenticate a user and store their ID in the session."""
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

    return jsonify({"message": "Login successful."}), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    """Log out the current session."""
    session.clear()
    return jsonify({"message": "Logout successful."}), 200
