
from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(
        __name__,
        template_folder="../frontend/templates",
        static_folder="../frontend/static",
        static_url_path="/static",
    )

    app.config.from_object("app.config.Config")

    db.init_app(app)

    from app.middleware.rate_limit import limiter
    from app.middleware.security_headers import register_security_headers
    from app.routes.auth_routes import auth_bp
    from app.routes.record_routes import record_bp
    from app.routes.audit_routes import audit_bp
    from app.routes.consent_routes import consent_bp
    from app.routes.authorization_routes import authorization_bp
    from app.routes.genai_routes import genai_bp
    from database import models
    from database.connection import init_database

    limiter.init_app(app)
    register_security_headers(app)

    init_database(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(record_bp)
    app.register_blueprint(audit_bp)
    app.register_blueprint(consent_bp)
    app.register_blueprint(authorization_bp)
    app.register_blueprint(genai_bp, url_prefix="/api/genai")

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/login")
    def login_page():
        return render_template("login.html")

    @app.route("/register")
    def register_page():
        return render_template("register.html")

    @app.route("/consent")
    def consent_page():
        return render_template("consent.html")

    @app.route("/record")
    def record_page():
        return render_template("record.html")

    @app.route("/authorization")
    def authorization_page():
        return render_template("authorization.html")

    @app.route("/audit")
    def audit_page():
        return render_template("audit.html")

    return app