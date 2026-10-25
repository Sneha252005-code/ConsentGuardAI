
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    db.init_app(app)

    from app.middleware.rate_limit import limiter
    from app.middleware.security_headers import register_security_headers
    from app.routes.auth_routes import auth_bp
    from database import models
    from database.connection import init_database
    from app.routes.consent_routes import consent_bp
    from app.routes.authorization_routes import authorization_bp

    limiter.init_app(app)
    register_security_headers(app)
    app.register_blueprint(auth_bp)

    init_database(app)
    app.register_blueprint(consent_bp)
    app.register_blueprint(authorization_bp)

    return app
