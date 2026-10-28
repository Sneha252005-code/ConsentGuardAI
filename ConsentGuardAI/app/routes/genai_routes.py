"""Generation routes with authorization, reuse checks, and audit logging."""

import logging

from flask import Blueprint, jsonify, request, session

from app.consent_context import consent_service
from audit.audit_service import record_event
from genai_gateway import GenAIGateway, MockProvider
from policy_engine.authorization import AuthorizationService
from policy_engine.reuse_detector import DataReuseDetector

logger = logging.getLogger(__name__)

genai_bp = Blueprint("genai", __name__)

gateway = GenAIGateway(provider=MockProvider())
authorization_service = AuthorizationService(consent_service)
reuse_detector = DataReuseDetector()


def log_audit_event(event_type, description, user_id):
    """Record an audit event without exposing internal errors to users."""
    try:
        record_event(
            event_type=event_type,
            description=description,
            user_id=user_id,
        )
    except Exception:
        logger.exception("Failed to record audit event: %s", event_type)


@genai_bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request must contain JSON."}), 400

    user_id_input = data.get("user_id")
    purpose = data.get("purpose")
    data_category = data.get("data_category")
    prompt = data.get("prompt")

    if not isinstance(user_id_input, str) or not user_id_input.strip():
        return jsonify({"error": "A valid user_id is required."}), 400

    if not isinstance(purpose, str) or not purpose.strip():
        return jsonify({"error": "A valid purpose is required."}), 400

    if not isinstance(data_category, str) or not data_category.strip():
        return jsonify({"error": "A valid data_category is required."}), 400

    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "A non-empty prompt is required."}), 400

    # Always use the authenticated session's user ID.
    session_user_id = session.get("user_id")

    if session_user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    try:
        authenticated_user_id = int(session_user_id)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authenticated user."}), 401

    purpose = purpose.strip()
    data_category = data_category.strip()
    prompt = prompt.strip()

    # Check for reuse of previously stored protected data.
    try:
        reuse = reuse_detector.detect(
            user_id=authenticated_user_id,
            prompt=prompt,
        )
    except Exception:
        logger.exception("Protected-data reuse check failed")

        log_audit_event(
            event_type="REUSE_CHECK_FAILED",
            description="Protected-data reuse verification failed.",
            user_id=authenticated_user_id,
        )

        return jsonify({
            "error": "Unable to verify protected-data reuse.",
            "decision": "BLOCK",
        }), 503

    if reuse.detected:
        log_audit_event(
            event_type="DATA_REUSE_DETECTED",
            description=(
                f"Protected-data reuse detected. "
                f"Record ID: {reuse.record_id}"
            ),
            user_id=authenticated_user_id,
        )

        return jsonify({
            "error": "Previously stored protected data was detected.",
            "decision": "WARN",
            "requires_consent_review": True,
            "record_id": reuse.record_id,
            "original_purpose": reuse.original_purpose,
            "reason": reuse.reason,
        }), 200

    # Check consent and authorization.
    try:
        decision = authorization_service.authorize(
            user_id=str(authenticated_user_id),
            purpose=purpose,
            data_category=data_category,
        )
    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid authorization request."
        }), 400
    except Exception:
        logger.exception("Authorization check failed")

        log_audit_event(
            event_type="AUTHORIZATION_CHECK_FAILED",
            description="Authorization verification failed.",
            user_id=authenticated_user_id,
        )

        return jsonify({
            "error": "Authorization check failed."
        }), 503

    if not decision.allowed:
        log_audit_event(
            event_type="AUTHORIZATION_DENIED",
            description=(
                f"Authorization denied for purpose: {purpose}; "
                f"category: {data_category}"
            ),
            user_id=authenticated_user_id,
        )

        return jsonify({
            "error": "Authorization denied.",
            "decision": "BLOCK",
            "reason": decision.reason,
        }), 403

    # Generate only after reuse and authorization checks pass.
    try:
        result = gateway.generate(prompt)
    except Exception:
        logger.exception("Generation failed")

        log_audit_event(
            event_type="GENERATION_FAILED",
            description="The generation provider raised an error.",
            user_id=authenticated_user_id,
        )

        return jsonify({
            "error": "Generation failed."
        }), 503

    if not result.get("success"):
        log_audit_event(
            event_type="GENERATION_FAILED",
            description="The generation provider returned a failure.",
            user_id=authenticated_user_id,
        )

        return jsonify({
            "error": result.get("message", "Generation failed.")
        }), 400

    log_audit_event(
        event_type="GENERATION_ALLOWED",
        description=(
            f"Generation completed for purpose: {purpose}; "
            f"category: {data_category}"
        ),
        user_id=authenticated_user_id,
    )

    return jsonify({
        "response": result["response"],
        "authorized": True,
        "decision": "ALLOW",
        "purpose": purpose,
        "data_category": data_category,
    }), 200