"""Generation routes with authorization, reuse checks, and context isolation."""

import logging
import uuid
from flask import Blueprint, jsonify, request, session, current_app

from app.consent_context import consent_service
from audit.audit_service import record_event
from database.repositories import (
    get_user_protected_records,
    create_protected_record,
    create_conversation,
    get_conversation,
    get_user_conversations,
    delete_conversation,
    create_chat_message,
    get_conversation_messages,
)
from genai_gateway import GenAIGateway, OpenAIProvider, MockProvider
from policy_engine.authorization import AuthorizationService
from policy_engine.decision_explanations import DecisionExplainer
from policy_engine.policy_rules import PolicyRules
from policy_engine.reuse_detector import DataReuseDetector
from security.encryption import encrypt_data

logger = logging.getLogger(__name__)

genai_bp = Blueprint("genai", __name__)

gateway = GenAIGateway()
policy_rules = PolicyRules()
reuse_detector = DataReuseDetector()
authorization_service = AuthorizationService(
    consent_service,
    policy_rules=policy_rules,
    reuse_detector=reuse_detector,
)
decision_explainer = DecisionExplainer()


def _get_authenticated_user_id(fallback_user_id_input=None):
    """Retrieve verified integer user ID from session or test context."""
    session_user_id = session.get("user_id")
    if session_user_id is not None:
        try:
            return int(session_user_id)
        except (TypeError, ValueError):
            return None

    # Allow numeric or valid string user_id in testing environments
    if current_app.config.get("TESTING") and fallback_user_id_input:
        try:
            return int(fallback_user_id_input)
        except (TypeError, ValueError):
            return 1  # Default test user
    return None


# ---------------------------------------------------------------------------
# Conversation Management Endpoints (Screen B - Isolated Contexts)
# ---------------------------------------------------------------------------

@genai_bp.route("/conversations", methods=["GET"])
def list_conversations():
    """List conversation sessions for the authenticated user."""
    user_id = _get_authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    conversations = get_user_conversations(user_id)
    return jsonify([
        {
            "id": conv.id,
            "title": conv.title,
            "created_at": conv.created_at.isoformat() if conv.created_at else "",
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else "",
        }
        for conv in conversations
    ]), 200


@genai_bp.route("/conversations", methods=["POST"])
def start_conversation():
    """Start a new isolated conversation session."""
    user_id = _get_authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True) or {}
    title = data.get("title", "New Conversation")

    conv = create_conversation(user_id=user_id, title=title)
    return jsonify({
        "id": conv.id,
        "title": conv.title,
        "created_at": conv.created_at.isoformat() if conv.created_at else "",
    }), 201


@genai_bp.route("/conversations/<conversation_id>", methods=["GET"])
def get_conversation_history(conversation_id):
    """Fetch all messages for an isolated conversation session."""
    user_id = _get_authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    conv = get_conversation(conversation_id)
    if not conv or conv.user_id != user_id:
        return jsonify({"error": "Conversation not found."}), 404

    messages = get_conversation_messages(conversation_id, user_id=user_id)
    return jsonify({
        "id": conv.id,
        "title": conv.title,
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "purpose": msg.purpose,
                "decision": msg.decision,
                "decision_reason": msg.decision_reason,
                "created_at": msg.created_at.isoformat() if msg.created_at else "",
            }
            for msg in messages
        ],
    }), 200


@genai_bp.route("/conversations/<conversation_id>", methods=["DELETE"])
def remove_conversation(conversation_id):
    """Delete an isolated conversation and its messages."""
    user_id = _get_authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    success = delete_conversation(conversation_id, user_id=user_id)
    if not success:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({"message": "Conversation deleted."}), 200


@genai_bp.route("/conversations/<conversation_id>", methods=["PATCH", "PUT"])
def rename_conversation(conversation_id):
    """Update conversation title."""
    user_id = _get_authenticated_user_id()
    if user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    data = request.get_json(silent=True) or {}
    new_title = data.get("title")
    if not new_title or not isinstance(new_title, str):
        return jsonify({"error": "Title is required."}), 400

    from database.repositories import update_conversation_title
    updated = update_conversation_title(conversation_id, new_title.strip()[:200], user_id=user_id)
    if not updated:
        return jsonify({"error": "Conversation not found."}), 404

    return jsonify({"id": updated.id, "title": updated.title}), 200


# ---------------------------------------------------------------------------
# Core Chat & Gatekeeper Endpoint (Objectives 1–4, Screens B & D)
# ---------------------------------------------------------------------------

@genai_bp.route("/generate", methods=["POST"])
def generate():
    """Process a chat request through the ConsentGuardAI verification pipeline.

    Workflow:
    Step 1: Track user data with source conversation and metadata if requested.
    Step 2: Record and preserve immutable original purpose.
    Step 3: Detect reuse of previously stored data across sessions.
    Step 4: Purpose comparison -> ALLOW / WARN / BLOCK decision.
    Step 5: Provider Gatekeeper -> only send to OpenAI on ALLOW.
    """
    data = request.get_json(silent=True)

    if not isinstance(data, dict) or not data:
        return jsonify({"error": "Request must contain JSON."}), 400

    user_id_input = data.get("user_id")
    session_uid = session.get("user_id")
    if user_id_input is None and session_uid is not None:
        user_id_input = str(session_uid)

    purpose = data.get("purpose")
    data_category = data.get("data_category", "General")
    prompt = data.get("prompt")
    conversation_id = data.get("conversation_id")
    track_as_record = data.get("track_as_record", False)
    record_title = data.get("record_title")
    data_classification = data.get("data_classification", "Confidential")

    # Strict input validation
    if not isinstance(user_id_input, str) or not user_id_input.strip():
        return jsonify({"error": "A valid user_id is required."}), 400

    if not isinstance(purpose, str) or not purpose.strip():
        return jsonify({"error": "A valid purpose is required."}), 400

    if not isinstance(data_category, str) or not data_category.strip():
        return jsonify({"error": "A valid data_category is required."}), 400

    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "A non-empty prompt is required."}), 400

    # Verify authenticated user identity
    authenticated_user_id = _get_authenticated_user_id(fallback_user_id_input=user_id_input)
    if authenticated_user_id is None:
        return jsonify({"error": "Authentication required."}), 401

    purpose = purpose.strip()
    data_category = data_category.strip()
    prompt = prompt.strip()
    request_ref = f"REQ-{uuid.uuid4().hex[:8].upper()}"

    # Ensure conversation session exists for context isolation
    conv = None
    if conversation_id:
        conv = get_conversation(conversation_id)
        if not conv or conv.user_id != authenticated_user_id:
            conv = None

    if conv is None:
        # Create a new session automatically
        conv_title = prompt[:30] + ("..." if len(prompt) > 30 else "")
        conv = create_conversation(user_id=authenticated_user_id, title=conv_title)
        conversation_id = conv.id

    # 1. Retrieve user's stored protected records
    try:
        user_records = get_user_protected_records(authenticated_user_id)
    except Exception:
        logger.exception("Failed to retrieve user protected records")
        user_records = []

    # 2. Objectives 3 & 4: Authorize request through reuse detection and purpose comparison
    try:
        auth_decision = authorization_service.authorize_prompt_request(
            user_id=str(authenticated_user_id),
            prompt=prompt,
            purpose=purpose,
            data_category=data_category,
            records=user_records,
        )
    except Exception as exc:
        logger.exception("Authorization pipeline check failed")
        record_event(
            event_type="AUTHORIZATION_CHECK_FAILED",
            description=f"Authorization verification error: {exc}",
            user_id=authenticated_user_id,
            conversation_id=conversation_id,
            request_ref=request_ref,
            decision="BLOCK",
            sent_to_provider=False,
        )
        return jsonify({
            "error": "Authorization verification failed.",
            "decision": "BLOCK",
            "reason": "Internal verification failure; access denied for security.",
            "sent_to_provider": False,
        }), 503

    # Save user message to database
    try:
        create_chat_message(
            conversation_id=conversation_id,
            user_id=authenticated_user_id,
            role="user",
            content=prompt,
            purpose=purpose,
            decision=auth_decision.decision,
            decision_reason=auth_decision.reason,
        )
    except Exception:
        logger.exception("Failed to store user message in DB")

    # Step 1 & 2: Identify and track data if requested or if confidential statement
    if track_as_record or data.get("track_data"):
        try:
            encrypted_content = encrypt_data(prompt).encode("utf-8")
            title = record_title or f"Tracked Data - {purpose}"
            new_record = create_protected_record(
                user_id=authenticated_user_id,
                title=title,
                data_encrypted=encrypted_content,
                original_purpose=purpose,  # Immutable original purpose
                conversation_id=conversation_id,
                description=f"Tracked data: {title}",
                data_classification=data_classification,
            )
            record_event(
                event_type="RECORD_TRACKED",
                description=f"Tracked data record #{new_record.id} with original purpose: '{purpose}'",
                user_id=authenticated_user_id,
                conversation_id=conversation_id,
                request_ref=request_ref,
                original_purpose=purpose,
                decision="ALLOW",
                sent_to_provider=False,
            )
        except Exception as exc:
            logger.exception("Failed to track record: %s", exc)

    # 3. Step 5: Provider Gatekeeper Enforcement
    # If decision is not ALLOW (i.e. WARN or BLOCK), NEVER send data to OpenAI
    explanation = decision_explainer.explain(auth_decision)

    if auth_decision.decision != "ALLOW":
        # Log audit event
        record_event(
            event_type=f"DATA_REUSE_{auth_decision.decision}" if auth_decision.reuse_detected else f"GENERATION_{auth_decision.decision}",
            description=auth_decision.reason,
            user_id=authenticated_user_id,
            conversation_id=conversation_id,
            request_ref=request_ref,
            reuse_detected=auth_decision.reuse_detected,
            matched_record_id=auth_decision.matched_record_id,
            original_purpose=auth_decision.original_purpose,
            requested_purpose=purpose,
            decision=auth_decision.decision,
            decision_reason=auth_decision.reason,
            sent_to_provider=False,
        )

        # Save assistant message with explanation to DB
        try:
            create_chat_message(
                conversation_id=conversation_id,
                user_id=authenticated_user_id,
                role="assistant",
                content=explanation.details,
                purpose=purpose,
                decision=auth_decision.decision,
                decision_reason=auth_decision.reason,
            )
        except Exception:
            pass

        return jsonify({
            "authorized": False,
            "decision": auth_decision.decision,
            "response": explanation.details,
            "reason": auth_decision.reason,
            "original_purpose": auth_decision.original_purpose,
            "requested_purpose": purpose,
            "matched_record_id": auth_decision.matched_record_id,
            "reuse_detected": auth_decision.reuse_detected,
            "requires_review": auth_decision.requires_review,
            "requires_consent_review": auth_decision.requires_review,
            "sent_to_provider": False,
            "conversation_id": conversation_id,
            "request_ref": request_ref,
        }), 200

    # 4. Request is ALLOWED -> Call AI Provider
    ai_response = None
    try:
        from genai_gateway.provider_client import generate_intelligent_response

        # Check if real OpenAI API key is configured
        api_key = current_app.config.get("OPENAI_API_KEY")
        if api_key and not api_key.startswith("your_") and not current_app.config.get("TESTING"):
            gateway.provider = OpenAIProvider(
                api_key=api_key,
                model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            )
        else:
            gateway.provider = MockProvider()

        gateway_result = gateway.generate(prompt)

        if not gateway_result.get("success"):
            # If rejected by prompt_filter (e.g. raw credentials), surface clear message
            if "sensitive information" in gateway_result.get("message", "").lower() or "unsafe instruction" in gateway_result.get("message", "").lower():
                ai_response = f"Gateway Security Filter: {gateway_result.get('message')}"
            else:
                ai_response = generate_intelligent_response(prompt)
        else:
            ai_response = gateway_result.get("response") or generate_intelligent_response(prompt)

    except Exception as exc:
        logger.exception("AI provider request failed")
        from genai_gateway.provider_client import generate_intelligent_response
        ai_response = generate_intelligent_response(prompt)

    # Save assistant message to DB
    try:
        create_chat_message(
            conversation_id=conversation_id,
            user_id=authenticated_user_id,
            role="assistant",
            content=ai_response,
            purpose=purpose,
            decision="ALLOW",
            decision_reason="Authorized for declared purpose",
        )
    except Exception:
        pass

    # Record successful generation audit event
    record_event(
        event_type="GENERATION_ALLOWED",
        description=f"Generation completed for purpose: '{purpose}'",
        user_id=authenticated_user_id,
        conversation_id=conversation_id,
        request_ref=request_ref,
        reuse_detected=auth_decision.reuse_detected,
        matched_record_id=auth_decision.matched_record_id,
        original_purpose=auth_decision.original_purpose,
        requested_purpose=purpose,
        decision="ALLOW",
        decision_reason=auth_decision.reason,
        sent_to_provider=True,
    )

    return jsonify({
        "authorized": True,
        "decision": "ALLOW",
        "response": ai_response,
        "reason": auth_decision.reason,
        "original_purpose": auth_decision.original_purpose,
        "requested_purpose": purpose,
        "matched_record_id": auth_decision.matched_record_id,
        "reuse_detected": auth_decision.reuse_detected,
        "requires_review": False,
        "sent_to_provider": True,
        "conversation_id": conversation_id,
        "request_ref": request_ref,
    }), 200
