
from functools import wraps

from flask import jsonify

from security.access_control import enforce_access


def consent_required(get_consent_record, get_requested_purpose):
    """
    Protect a route using the consent-policy decision.
    Both arguments must be functions that retrieve values for the request.
    """

    def decorator(view_function):
        @wraps(view_function)
        def wrapped_view(*args, **kwargs):
            try:
                consent_record = get_consent_record()
                requested_purpose = get_requested_purpose()

                allowed = enforce_access(
                    consent_record=consent_record,
                    requested_purpose=requested_purpose,
                )
            except Exception:
                allowed = False

            if not allowed:
                return jsonify({
                    "error": "Access denied: valid consent is required."
                }), 403

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator
