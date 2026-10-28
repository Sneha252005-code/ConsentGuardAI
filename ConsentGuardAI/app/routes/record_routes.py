
"""API routes for encrypted protected records."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

from app import db
from database.repositories import (
    create_protected_record,
    get_protected_record,
    get_user_protected_records,
    delete_protected_record,
)
from security.encryption import encrypt_data, EncryptionError

record_bp = Blueprint("records", __name__, url_prefix="/api/records")


def _authenticated_user_id():
    """Return the authenticated user's database ID."""
    if not current_user.is_authenticated:
        return None
    return current_user.get_id()


@record_bp.route("", methods=["POST"])
def create_record():
    """Encrypt and save a record for the authenticated user."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    title = data.get("title")
    content = data.get("content")
    purpose = data.get("original_purpose")

    if not all(
        isinstance(value, str) and value.strip()
        for value in (title, content, purpose)
    ):
        return jsonify({
            "error": "title, content, and original_purpose are required."
        }), 400

    if len(title.strip()) > 200 or len(purpose.strip()) > 500:
        return jsonify({
            "error": "Title or purpose exceeds the allowed length."
        }), 400

    try:
        encrypted_data = encrypt_data(content.strip())
    except EncryptionError:
        return jsonify({
            "error": "Unable to securely encrypt this record."
        }), 503

    try:
        record = create_protected_record(
            user_id=int(user_id),
            title=title.strip(),
            data_encrypted=encrypted_data.encode("utf-8"),
            original_purpose=purpose.strip(),
        )
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to save this record."}), 500

    return jsonify({
        "id": record.id,
        "title": record.title,
        "original_purpose": record.original_purpose,
        "created_at": record.created_at.isoformat(),
    }), 201


@record_bp.route("", methods=["GET"])
def list_records():
    """List records belonging to the authenticated user."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

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
    """Return metadata only for a record owned by the current user."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    record = get_protected_record(record_id)

    if record is None or record.user_id != int(user_id):
        return jsonify({"error": "Record not found."}), 404

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
        return jsonify({"error": "Authentication required."}), 401

    record = get_protected_record(record_id)

    if record is None or record.user_id != int(user_id):
        return jsonify({"error": "Record not found."}), 404

    try:
        delete_protected_record(record_id)
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to delete record."}), 500

    return jsonify({"message": "Record deleted."}), 200
