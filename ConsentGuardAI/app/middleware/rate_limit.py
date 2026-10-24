
from flask import jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[],
    storage_uri="memory://",
)


def login_rate_limit(view_function):
    """Limit repeated login attempts from the same IP address."""
    return limiter.limit(
        "5 per minute",
        error_message="Too many login attempts. Please try again later.",
    )(view_function)


def register_rate_limit(view_function):
    """Limit repeated registration requests."""
    return limiter.limit(
        "5 per minute",
        error_message="Too many registration attempts. Please try again later.",
    )(view_function)
