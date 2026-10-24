
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def create_app():
    app = Flask(__name__)
    app.config.from_object("app.config.Config")

    db.init_app(app)

    from database import models
    from database.connection import init_database
    from app.routes.consent_routes import consent_bp

    init_database(app)
    app.register_blueprint(consent_bp)

    return app

