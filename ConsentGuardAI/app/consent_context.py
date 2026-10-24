
"""Shared consent service for the API routes."""

from app import db
from consent.consent_service import ConsentService
from database.repositories import ConsentDatabaseRepository

consent_service = ConsentService(ConsentDatabaseRepository())
