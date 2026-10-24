
"""API routes for checking consent-based authorization."""

from flask import Blueprint, jsonify, request

from consent.consent_repository import ConsentRepository
from consent.consent_service import ConsentService
from policy_engine.authorization import AuthorizationService

authorization_bp = Blueprint(
    "authorization",
    __name__,
    url_prefix="/api/authorization",
)

# Temporary in-memory service.
# This repository must eventually be shared with the consent API.
_consent_service = ConsentService(ConsentRepository())
_authorization_service = AuthorizationService(_consent_service)


@authorization_bp.route("/check", methods=["POST"])
def check_authorization():
    """Check authorization for each requested data category."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request body must be a JSON object."}), 400

    user_id = data.get("user_id")
    purpose = data.get("purpose")
    data_categories = data.get("data_categories")

    if not isinstance(user_id, str) or not user_id.strip():
        return jsonify({"error": "user_id must be a non-empty string."}), 400

    if not isinstance(purpose, str) or not purpose.strip():
        return jsonify({"error": "purpose must be a non-empty string."}), 400

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

    decisions = []

    try:
        for category in data_categories:
            decision = _authorization_service.authorize(
                user_id=user_id,
                purpose=purpose,
                data_category=category,
            )
            decisions.append(decision)
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    allowed = all(decision.allowed for decision in decisions)
    reasons = [
        decision.reason
        for decision in decisions
        if not decision.allowed
    ]

    return jsonify({
        "authorized": allowed,
        "reason": "; ".join(reasons) if reasons else "Authorization granted.",
        "decisions": [
            {
                "data_category": decision.data_category,
                "authorized": decision.allowed,
                "reason": decision.reason,
            }
            for decision in decisions
        ],
    }), 200
