
"""API routes for protected records."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

from database.repositories import (
    create_protected_record,
    get_protected_record,
    get_user_protected_records,
    delete_protected_record,
)

record_bp = Blueprint("records", __name__, url_prefix="/api/records")


def _authenticated_user_id():
    """Return the current user's ID, or None if unauthenticated."""
    if not current_user.is_authenticated:
        return None
    return current_user.get_id()


@record_bp.route("", methods=["POST"])
def create_record():
    """Create a protected record for the authenticated user."""
    user_id = _authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    data = request.get_json(silent=True) or {}
    title = data.get("title")
    encrypted_data = data.get("data_encrypted")
    purpose = data.get("original_purpose")

    if not all(isinstance(value, str) and value.strip()
               for value in (title, encrypted_data, purpose)):
        return jsonify({
            "error": "title, data_encrypted, and original_purpose are required"
        }), 400

    record = create_protected_record(
        user_id=user_id,
        title=title.strip(),
        data_encrypted=encrypted_data.encode("utf-8"),
        original_purpose=purpose.strip(),
    )

    return jsonify({
        "id": record.id,
        "title": record.title,
        "original_purpose": record.original_purpose,
        "created_at": record.created_at.isoformat(),
    }), 201


@record_bp.route("", methods=["GET"])
def list_records():
    """List protected records belonging to the authenticated user."""
    user_id = _authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    records = get_user_protected_records(int(user_id))
    return jsonify([
        {
            "id": record.id,
            "title": record.title,
            "original_purpose": record.original_purpose,
            "created_at": record.created_at.isoformat(),
        }
        for record in records
    ]), 200


@record_bp.route("/<int:record_id>", methods=["GET"])
def retrieve_record(record_id):
    """Retrieve a record only if it belongs to the current user."""
    user_id = _authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    record = get_protected_record(record_id)
    if record is None or record.user_id != int(user_id):
        return jsonify({"error": "Record not found"}), 404

    return jsonify({
        "id": record.id,
        "title": record.title,
        "original_purpose": record.original_purpose,
        "created_at": record.created_at.isoformat(),
    }), 200


@record_bp.route("/<int:record_id>", methods=["DELETE"])
def remove_record(record_id):
    """Delete a record only if it belongs to the current user."""
    user_id = _authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    record = get_protected_record(record_id)
    if record is None or record.user_id != int(user_id):
        return jsonify({"error": "Record not found"}), 404

    delete_protected_record(record_id)
    return jsonify({"message": "Record deleted"}), 200
