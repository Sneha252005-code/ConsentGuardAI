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

    limiter.init_app(app)
    register_security_headers(app)
    app.register_blueprint(auth_bp)

    return app