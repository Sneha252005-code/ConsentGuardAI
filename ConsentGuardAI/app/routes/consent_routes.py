"""API routes for purpose-specific consent management with audit logging."""

import logging
from flask import Blueprint, jsonify, request, session, current_app

from app.consent_context import consent_service
from audit.audit_service import record_event

logger = logging.getLogger(__name__)

consent_bp = Blueprint(
    "consent",
    __name__,
    url_prefix="/api/consent",
)


def _authenticated_user_id(fallback_user_id=None):
    """Return the authenticated user's integer database ID from the secure session."""
    session_user_id = session.get("user_id")
    if session_user_id is not None:
        try:
            return int(session_user_id)
        except (TypeError, ValueError):
            return None

    if current_app.config.get("TESTING") and fallback_user_id is not None:
        try:
            return int(fallback_user_id)
        except (TypeError, ValueError):
            return 1
    elif current_app.config.get("TESTING"):
        return 1

    return None


@consent_bp.post("/")
def grant_consent():
    """Grant consent for specific data categories and a purpose."""
    auth_user_id = _authenticated_user_id()
    if auth_user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return jsonify({"error": "A JSON object is required."}), 400

    user_id = payload.get("user_id")
    if not user_id or not isinstance(user_id, str) or not user_id.strip():
        user_id = str(auth_user_id)

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
            user_id=user_id.strip(),
            purpose=purpose.strip(),
            data_categories=[c.strip() for c in categories],
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    # Record audit event using the authenticated user's integer session ID
    try:
        categories_str = ", ".join(record.data_categories)
        record_event(
            event_type="CONSENT_GRANTED",
            description=(
                f"Consent scope granted (Consent ID: {record.id}) for purpose '{record.purpose}' "
                f"with permitted data categories: [{categories_str}]"
            ),
            user_id=auth_user_id,
            request_ref=f"CS-{record.id[:8].upper()}",
            original_purpose=record.purpose,
            requested_purpose=record.purpose,
            decision="ALLOW",
            decision_reason=f"Explicit user consent granted for categories: {categories_str}",
            sent_to_provider=False,
        )
    except Exception as exc:
        logger.exception("Failed to record consent grant audit event: %s", exc)

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
        "consent_id": record.id,
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
    auth_user_id = _authenticated_user_id()
    if auth_user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    try:
        record = consent_service.withdraw_consent(consent_id)
    except KeyError:
        return jsonify({"error": "Consent not found."}), 404

    # Record audit event using the authenticated user's integer session ID
    try:
        record_event(
            event_type="CONSENT_WITHDRAWN",
            description=(
                f"Consent scope withdrawn (Consent ID: {record.id}) for purpose '{record.purpose}'. "
                f"Future reuse and generation requests under this scope are denied."
            ),
            user_id=auth_user_id,
            request_ref=f"CS-WD-{record.id[:8].upper()}",
            original_purpose=record.purpose,
            requested_purpose=record.purpose,
            decision="BLOCK",
            decision_reason="Consent scope revoked by user; future access denied",
            sent_to_provider=False,
        )
    except Exception as exc:
        logger.exception("Failed to record consent withdrawal audit event: %s", exc)

    return jsonify({
        "consent_id": record.id,
        "granted": record.granted,
        "withdrawn_at": (
            record.withdrawn_at.isoformat()
            if record.withdrawn_at else None
        ),
        "message": "Consent withdrawn.",
    }), 200
