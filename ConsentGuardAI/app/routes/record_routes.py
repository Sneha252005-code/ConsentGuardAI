"""API routes for encrypted protected records (Objectives 1 & 2, Screen C)."""

from flask import Blueprint, jsonify, request, session

from app import db
from database.repositories import (
    create_protected_record,
    get_protected_record,
    get_user_protected_records,
    delete_protected_record,
)
from audit.audit_service import record_event
from security.encryption import encrypt_data, EncryptionError

record_bp = Blueprint("records", __name__, url_prefix="/api/records")


def _authenticated_user_id():
    """Return the authenticated user's database ID from the secure session."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


@record_bp.route("", methods=["POST"])
def create_record():
    """Encrypt and save a protected record with immutable original purpose (Objectives 1 & 2)."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    title = data.get("title")
    content = data.get("content")
    purpose = data.get("original_purpose")
    conversation_id = data.get("conversation_id")
    description = data.get("description")
    classification = data.get("data_classification", "Confidential")

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
            conversation_id=conversation_id.strip() if conversation_id else None,
            description=description.strip() if description else f"Tracked record for {title.strip()}",
            data_classification=classification.strip() if classification else "Confidential",
        )

        record_event(
            event_type="RECORD_TRACKED",
            description=f"Tracked data record #{record.id} with original purpose: '{record.original_purpose}'",
            user_id=int(user_id),
            conversation_id=conversation_id,
            original_purpose=record.original_purpose,
            decision="ALLOW",
        )
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to save this record."}), 500

    return jsonify({
        "id": record.id,
        "title": record.title,
        "description": record.description,
        "source_conversation": record.conversation_id or "Direct Submission",
        "data_classification": record.data_classification,
        "original_purpose": record.original_purpose,
        "created_at": record.created_at.isoformat(),
    }), 201


@record_bp.route("", methods=["GET"])
def list_records():
    """List records belonging to the authenticated user without exposing confidential plaintext."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    records = get_user_protected_records(int(user_id))

    return jsonify([
        {
            "id": record.id,
            "title": record.title,
            "description": record.description or f"Tracked data: {record.title}",
            "source_conversation": record.conversation_id or "Session Direct",
            "data_classification": record.data_classification or "Confidential",
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
        "description": record.description or f"Tracked data: {record.title}",
        "source_conversation": record.conversation_id or "Session Direct",
        "data_classification": record.data_classification or "Confidential",
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
        record_event(
            event_type="RECORD_DELETED",
            description=f"Deleted protected record #{record_id}",
            user_id=int(user_id),
        )
    except Exception:
        db.session.rollback()
        return jsonify({"error": "Unable to delete record."}), 500

    return jsonify({"message": "Record deleted."}), 200
