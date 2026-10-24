
"""Database initialization helpers for ConsentGuardAI."""


def init_database(app) -> None:
    """Create registered database tables within the Flask app context."""
    from app import db
    from database import models  # noqa: F401

    with app.app_context():
        db.create_all()
