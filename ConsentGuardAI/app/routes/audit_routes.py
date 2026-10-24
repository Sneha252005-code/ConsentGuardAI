
"""API routes for audit logs."""

from flask import Blueprint, jsonify, request
from flask_login import current_user

from audit.audit_service import fetch_recent_events
from audit.integrity import verify_audit_chain

audit_bp = Blueprint("audit", __name__, url_prefix="/api/audit")


@audit_bp.route("", methods=["GET"])
def list_audit_events():
    """Return recent audit events belonging to the authenticated user."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    try:
        limit = int(request.args.get("limit", 50))
    except (TypeError, ValueError):
        return jsonify({"error": "limit must be an integer"}), 400

    if not 1 <= limit <= 100:
        return jsonify({"error": "limit must be between 1 and 100"}), 400

    events = fetch_recent_events(limit=limit)
    user_id = int(current_user.get_id())

    # Only return events associated with the current user.
    user_events = [
        event for event in events
        if event.user_id == user_id
    ]

    return jsonify([
        {
            "id": event.id,
            "event_type": event.event_type,
            "description": event.description,
            "created_at": event.created_at.isoformat(),
        }
        for event in user_events
    ]), 200


@audit_bp.route("/integrity", methods=["GET"])
def check_audit_integrity():
    """Check the integrity of the available audit history."""
    if not current_user.is_authenticated:
        return jsonify({"error": "Authentication required"}), 401

    events = fetch_recent_events(limit=100)
    user_id = int(current_user.get_id())

    user_events = [
        event for event in events
        if event.user_id == user_id
    ]

    is_valid = verify_audit_chain(user_events)

    return jsonify({
        "integrity_valid": is_valid,
        "entries_checked": len(user_events),
    }), 200
