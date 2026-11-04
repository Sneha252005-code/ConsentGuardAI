"""API routes for checking consent-based authorization and purpose reuse (Objectives 3 & 4, Screen D)."""

from flask import Blueprint, jsonify, request, session

from app.consent_context import consent_service
from database.repositories import get_user_protected_records
from policy_engine.authorization import AuthorizationService
from policy_engine.policy_rules import PolicyRules
from policy_engine.reuse_detector import DataReuseDetector

authorization_bp = Blueprint(
    "authorization",
    __name__,
    url_prefix="/api/authorization",
)

policy_rules = PolicyRules()
reuse_detector = DataReuseDetector()
_authorization_service = AuthorizationService(
    consent_service,
    policy_rules=policy_rules,
    reuse_detector=reuse_detector,
)


def _get_authenticated_user_id():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


@authorization_bp.route("/inspect", methods=["POST"])
def inspect_reuse_and_purpose():
    """Interactive Reuse Detection and Purpose Authorization inspection (Screen D)."""
    user_id = _get_authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True) or {}
    prompt = data.get("prompt", "")
    purpose = data.get("purpose", "")
    data_category = data.get("data_category", "General")

    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "Prompt is required."}), 400

    if not isinstance(purpose, str) or not purpose.strip():
        return jsonify({"error": "Purpose is required."}), 400

    user_records = get_user_protected_records(user_id)
    match = reuse_detector.detect_in_records(prompt=prompt, records=user_records)
    auth_decision = _authorization_service.authorize_prompt_request(
        user_id=str(user_id),
        prompt=prompt,
        purpose=purpose,
        data_category=data_category,
        records=user_records,
    )

    return jsonify({
        "reuse_detected": match.detected,
        "match_type": match.match_type or "none",
        "matched_record_id": match.record_id,
        "matched_snippet": match.matched_snippet,
        "data_classification": match.data_classification or "Confidential",
        "original_purpose": match.original_purpose or "—",
        "requested_purpose": purpose,
        "decision": auth_decision.decision,
        "authorized": auth_decision.allowed,
        "reason": auth_decision.reason,
        "requires_review": auth_decision.requires_review,
    }), 200


@authorization_bp.route("/check", methods=["POST"])
def check_authorization():
    """Check authorization for each requested data category (Legacy Category Check)."""
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
        "reason": (
            "; ".join(reasons)
            if reasons else "Authorization granted."
        ),
        "decisions": [
            {
                "data_category": decision.data_category,
                "authorized": decision.allowed,
                "reason": decision.reason,
            }
            for decision in decisions
        ],
    }), 200
