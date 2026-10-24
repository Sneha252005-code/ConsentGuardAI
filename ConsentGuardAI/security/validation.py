
import re
from typing import Any


EMAIL_PATTERN = re.compile(
    r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
)

DEFAULT_MAX_LENGTH = 2000


def validate_email(email: Any) -> str:
    """Validate and normalize an email address."""
    if not isinstance(email, str):
        raise ValueError("Email must be text.")

    email = email.strip().lower()

    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise ValueError("Enter a valid email address.")

    return email


def validate_password(password: Any) -> str:
    """Validate password input without modifying the password."""
    if not isinstance(password, str):
        raise ValueError("Password must be text.")

    if len(password) < 12:
        raise ValueError("Password must contain at least 12 characters.")

    if len(password) > 128:
        raise ValueError("Password cannot exceed 128 characters.")

    if password.isspace() or not password:
        raise ValueError("Password cannot be empty.")

    return password


def validate_text(
    value: Any,
    field_name: str = "Input",
    max_length: int = DEFAULT_MAX_LENGTH,
) -> str:
    """Validate ordinary text fields and enforce length limits."""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text.")

    if not isinstance(max_length, int) or max_length < 1:
        raise ValueError("Maximum length must be a positive integer.")

    value = value.strip()

    if not value:
        raise ValueError(f"{field_name} cannot be empty.")

    if len(value) > max_length:
        raise ValueError(
            f"{field_name} cannot exceed {max_length} characters."
        )

    return value
