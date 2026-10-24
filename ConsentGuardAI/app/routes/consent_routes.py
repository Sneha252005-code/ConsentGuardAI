
"""API routes for purpose-specific consent management."""

from flask import Blueprint, jsonify, request

from app.consent_context import consent_service

consent_bp = Blueprint(
    "consent",
    __name__,
    url_prefix="/api/consent",
)


@consent_bp.post("/")
def grant_consent():
    """Grant consent for specific data categories and a purpose."""
    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    user_id = payload.get("user_id")
    purpose = payload.get("purpose")
    categories = payload.get("data_categories")

    if not isinstance(user_id, str) or not user_id.strip():
        return jsonify({"error": "user_id must be a non-empty string."}), 400

    if not isinstance(purpose, str) or not purpose.strip():
        return jsonify({"error": "purpose must be a non-empty string."}), 400

    if (
        not isinstance(categories, list)
        or not categories
        or not all(
            isinstance(item, str) and item.strip()
            for item in categories
        )
    ):
        return jsonify({
            "error": "data_categories must be a non-empty list of strings."
        }), 400

    try:
        record = consent_service.grant_consent(
            user_id=user_id,
            purpose=purpose,
            data_categories=categories,
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    return jsonify({
        "consent_id": record.id,
        "user_id": record.user_id,
        "purpose": record.purpose,
        "data_categories": list(record.data_categories),
        "granted": record.granted,
    }), 201


@consent_bp.get("/<consent_id>")
def get_consent(consent_id):
    """Retrieve a consent record."""
    record = consent_service.get_consent(consent_id)

    if record is None:
        return jsonify({"error": "Consent not found."}), 404

    return jsonify({
        "consent_id": record.consent_id,
        "user_id": record.user_id,
        "purpose": record.purpose,
        "data_categories": list(record.data_categories),
        "granted": record.granted,
        "withdrawn_at": (
            record.withdrawn_at.isoformat()
            if record.withdrawn_at else None
        ),
    }), 200


@consent_bp.post("/<consent_id>/withdraw")
def withdraw_consent(consent_id):
    """Withdraw an existing consent record."""
    try:
        record = consent_service.withdraw_consent(consent_id)
    except KeyError:
        return jsonify({"error": "Consent not found."}), 404

    return jsonify({
        "consent_id": record.id,
        "granted": record.granted,
        "withdrawn_at": (
            record.withdrawn_at.isoformat()
            if record.withdrawn_at else None
        ),
        "message": "Consent withdrawn.",
    }), 200
