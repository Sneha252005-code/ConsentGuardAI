
from security.access_control import enforce_access


def test_missing_consent_is_denied():
    assert enforce_access(
        None,
        "research",
        lambda record, purpose: record is not None,
    ) is False


def test_withdrawn_consent_is_denied():
    consent = {"status": "withdrawn"}

    assert enforce_access(
        consent,
        "research",
        lambda record, purpose: record.get("status") == "active",
    ) is False


def test_purpose_mismatch_is_denied():
    consent = {"status": "active", "purpose": "research"}

    assert enforce_access(
        consent,
        "marketing",
        lambda record, purpose: (
            record.get("status") == "active"
            and record.get("purpose") == purpose
        ),
    ) is False
