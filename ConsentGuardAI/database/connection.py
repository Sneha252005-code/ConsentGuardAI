
"""Database connection and initialization helpers for ConsentGuardAI."""

from app import db


def get_database():
    """Return the application's shared SQLAlchemy database object."""
    return db


def init_database(app) -> None:
    """Create registered database tables within the Flask app context."""
    from database import models  # noqa: F401

    with app.app_context():
        db.create_all()
