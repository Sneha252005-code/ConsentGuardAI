from flask import Flask
from app.routes.genai_routes import genai_bp


def create_test_app():
    app = Flask(__name__)
    app.register_blueprint(genai_bp, url_prefix="/genai")
    app.config["TESTING"] = True
    return app


def test_generate_rejects_missing_json():
    client = create_test_app().test_client()
    response = client.post("/genai/generate")
    assert response.status_code == 400


def test_generate_rejects_empty_json():
    client = create_test_app().test_client()
    response = client.post("/genai/generate", json={})
    assert response.status_code == 400


def test_generate_rejects_missing_prompt():
    client = create_test_app().test_client()
    response = client.post("/genai/generate", json={
        "user_id": "test-user",
        "purpose": "research",
        "data_category": "basic",
    })
    assert response.status_code == 400


def test_generate_rejects_blank_user_id():
    client = create_test_app().test_client()
    response = client.post("/genai/generate", json={
        "user_id": " ",
        "purpose": "research",
        "data_category": "basic",
        "prompt": "Summarize records",
    })
    assert response.status_code == 400
