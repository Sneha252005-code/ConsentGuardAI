
"""Database connection helpers for ConsentGuardAI."""

from app import db


def get_database():
    """Return the application's shared SQLAlchemy database object."""
    return db
