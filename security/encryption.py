
import base64
import os

from cryptography.fernet import Fernet, InvalidToken


class EncryptionError(Exception):
    """Raised when protected data cannot be encrypted or decrypted."""


def generate_encryption_key() -> str:
    """Generate a new Fernet key. Run once and store it securely."""
    return Fernet.generate_key().decode("utf-8")


def _get_cipher() -> Fernet:
    """Load the encryption key from application configuration."""
    key = os.getenv("DATA_ENCRYPTION_KEY")

    if not key:
        try:
            from flask import current_app, has_app_context

            if has_app_context():
                key = current_app.config.get("DATA_ENCRYPTION_KEY")
        except ImportError:
            pass

    if not isinstance(key, str) or not key.strip():
        raise EncryptionError("Encryption key is not configured.")

    try:
        return Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise EncryptionError("Encryption key is invalid.") from exc


def encrypt_data(plaintext: str) -> str:
    """Encrypt text and return a URL-safe encoded ciphertext."""
    if not isinstance(plaintext, str):
        raise ValueError("Data to encrypt must be text.")

    try:
        ciphertext = _get_cipher().encrypt(plaintext.encode("utf-8"))
        return ciphertext.decode("utf-8")
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError("Data encryption failed.") from exc


def decrypt_data(ciphertext: str) -> str:
    """Decrypt ciphertext. Never return plaintext if decryption fails."""
    if not isinstance(ciphertext, str) or not ciphertext:
        raise ValueError("Ciphertext must be a non-empty string.")

    try:
        plaintext = _get_cipher().decrypt(ciphertext.encode("utf-8"))
        return plaintext.decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError(
            "Decryption failed: invalid ciphertext or encryption key."
        ) from exc
    except EncryptionError:
        raise
    except Exception as exc:
        raise EncryptionError("Data decryption failed.") from exc
from dotenv import load_dotenv

load_dotenv()