"""Shared consent service for the API routes."""

from consent.consent_repository import ConsentRepository
from consent.consent_service import ConsentService

consent_service = ConsentService(ConsentRepository())