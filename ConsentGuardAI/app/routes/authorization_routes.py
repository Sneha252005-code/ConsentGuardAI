
"""API routes for checking consent-based authorization."""

from flask import Blueprint, jsonify, request

from policy_engine.authorization import AuthorizationService
from consent.consent_service import ConsentService
from consent.consent_repository import ConsentRepository

authorization_bp = Blueprint(
    "authorization",
    __name__,
    url_prefix="/api/authorization",
)

# Uses the same in-memory consent approach as the current consent API.
_consent_service = ConsentService(ConsentRepository())
_authorization_service = AuthorizationService(_consent_service)


@authorization_bp.route("/check", methods=["POST"])
def check_authorization():
    """Check whether a user is authorized for a purpose and data categories."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Request body must be a JSON object."
        }), 400

    user_id = data.get("user_id")
    purpose = data.get("purpose")
    data_categories = data.get("data_categories")

    if not user_id or not isinstance(user_id, str):
        return jsonify({"error": "user_id is required."}), 400

    if not purpose or not isinstance(purpose, str):
        return jsonify({"error": "purpose is required."}), 400

    if (
        not isinstance(data_categories, list)
        or not data_categories
        or not all(
            isinstance(category, str) and category.strip()
            for category in data_categories
        )
    ):
        return jsonify({
            "error": "data_categories must be a non-empty list of strings."
        }), 400

    try:
        decision = _authorization_service.authorize(
            user_id=user_id,
            purpose=purpose,
            data_categories=data_categories,
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    allowed = getattr(decision, "allowed", False)
    reason = getattr(decision, "reason", None)

    return jsonify({
        "authorized": bool(allowed),
        "reason": reason or (
            "Authorization granted."
            if allowed
            else "Authorization denied."
        ),
    }), 200
