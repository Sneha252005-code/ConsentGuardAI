"""Application configuration for ConsentGuardAI."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Search and load local environment variables before reading configuration.
_base_dir = Path(__file__).resolve().parent
for _candidate in [
    _base_dir / ".env",
    _base_dir.parent / ".env",
    Path.cwd() / ".env",
    Path.cwd() / "ConsentGuardAI" / ".env",
]:
    if _candidate.is_file():
        load_dotenv(dotenv_path=_candidate)
        break
else:
    load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")

    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///consentguardai.db",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DATA_ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY")

    # OpenAI configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = (
        os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    )
