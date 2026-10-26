
from flask import Blueprint, jsonify, request

from app.consent_context import consent_service
from genai_gateway import GenAIGateway, MockProvider
from policy_engine.authorization import AuthorizationService

genai_bp = Blueprint("genai", __name__)

gateway = GenAIGateway(provider=MockProvider())
authorization_service = AuthorizationService(consent_service)


@genai_bp.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Request must contain JSON."}), 400

    user_id = data.get("user_id")
    purpose = data.get("purpose")
    data_category = data.get("data_category")
    prompt = data.get("prompt")

    if not isinstance(user_id, str) or not user_id.strip():
        return jsonify({"error": "A valid user_id is required."}), 400

    if not isinstance(purpose, str) or not purpose.strip():
        return jsonify({"error": "A valid purpose is required."}), 400

    if not isinstance(data_category, str) or not data_category.strip():
        return jsonify({"error": "A valid data_category is required."}), 400

    if not isinstance(prompt, str) or not prompt.strip():
        return jsonify({"error": "A non-empty prompt is required."}), 400

    try:
        decision = authorization_service.authorize(
            user_id=user_id,
            purpose=purpose,
            data_category=data_category,
        )
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid authorization request."}), 400
    except Exception:
        return jsonify({"error": "Authorization check failed."}), 503

    if not decision.allowed:
        return jsonify({
            "error": "Authorization denied.",
            "reason": decision.reason,
        }), 403

    result = gateway.generate(prompt)

    if not result["success"]:
        return jsonify({"error": result["message"]}), 400

    return jsonify({
        "response": result["response"],
        "authorized": True,
        "purpose": purpose,
        "data_category": data_category,
    }), 200
