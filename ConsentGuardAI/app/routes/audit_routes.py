"""API routes for audit logs and live privacy dashboard statistics (Screens A & E)."""

from flask import Blueprint, jsonify, request, session

from audit.audit_service import fetch_recent_events
from audit.integrity import verify_audit_chain
from database.repositories import get_dashboard_stats

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


def _authenticated_user_id():
    """Return the logged-in user's ID from the secure Flask session."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


@audit_bp.route("/stats", methods=["GET"])
def dashboard_stats():
    """Return real database-backed statistics for Screen A (Privacy Dashboard)."""
    user_id = _authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    stats = get_dashboard_stats(user_id=user_id)
    return jsonify(stats), 200


@audit_bp.route("", methods=["GET"])
def list_audit_events():
    """Return recent structured audit events for the logged-in user (Screen E)."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    try:
        limit = int(request.args.get("limit", 100))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

    if not 1 <= limit <= 200:
        return jsonify({"error": "limit must be between 1 and 200"}), 400

    events = fetch_recent_events(limit=limit, user_id=user_id)

    return jsonify([
        {
            "id": event.id,
            "request_ref": event.request_ref or f"REQ-{event.id}",
            "conversation_id": event.conversation_id or "—",
            "event_type": event.event_type,
            "user_id": event.user_id,
            "description": event.description,
            "reuse_detected": bool(event.reuse_detected),
            "matched_record_id": event.matched_record_id,
            "original_purpose": event.original_purpose or "—",
            "requested_purpose": event.requested_purpose or "—",
            "decision": event.decision or "—",
            "decision_reason": event.decision_reason or event.description,
            "sent_to_provider": bool(event.sent_to_provider),
            "created_at": (
                event.created_at.isoformat()
                if event.created_at else ""
            ),
        }
        for event in events
    ]), 200


@audit_bp.route("/integrity", methods=["GET"])
def check_audit_integrity():
    """Check cryptographic hash-chain integrity of the stored audit history."""
    user_id = _authenticated_user_id()

    if user_id is None:
        return jsonify({"error": "Authentication required"}), 401

    from database.models import AuditLog
    events = AuditLog.query.order_by(AuditLog.created_at.asc(), AuditLog.id.asc()).all()

    return jsonify({
        "integrity_valid": verify_audit_chain(events),
        "entries_checked": len(events),
    }), 200
