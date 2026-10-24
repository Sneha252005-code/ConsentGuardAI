
from argon2 import PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)


_password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Return an Argon2 hash of a user's password."""
    if not isinstance(password, str):
        raise ValueError("Password must be text.")

    if not 12 <= len(password) <= 128:
        raise ValueError(
            "Password must contain between 12 and 128 characters."
        )

    if password.isspace():
        raise ValueError("Password cannot be empty.")

    try:
        return _password_hasher.hash(password)
    except HashingError as exc:
        raise RuntimeError("Password hashing failed.") from exc


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password without exposing verification details."""
    if not isinstance(password_hash, str) or not isinstance(password, str):
        return False

    try:
        return _password_hasher.verify(password_hash, password)
    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
    ):
        return False


def password_hash_needs_update(password_hash: str) -> bool:
    """Check whether an existing hash needs stronger parameters."""
    if not isinstance(password_hash, str):
        return False

    try:
        return _password_hasher.check_needs_rehash(password_hash)
    except (InvalidHashError, VerificationError):
        return False
