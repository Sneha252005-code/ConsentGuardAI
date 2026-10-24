
from security.access_control import enforce_access


def test_access_allowed_when_policy_returns_true():
    assert enforce_access(
        {"consent": True},
        "research",
        lambda record, purpose: True,
    ) is True


def test_access_denied_when_policy_returns_false():
    assert enforce_access(
        {"consent": True},
        "research",
        lambda record, purpose: False,
    ) is False


def test_access_denied_when_purpose_is_empty():
    assert enforce_access(
        {"consent": True},
        " ",
        lambda record, purpose: True,
    ) is False


def test_access_denied_when_policy_fails():
    def failing_policy(record, purpose):
        raise RuntimeError("Policy check failed")

    assert enforce_access(
        {"consent": True},
        "research",
        failing_policy,
    ) is False


def test_access_denied_when_policy_engine_is_unavailable():
    assert enforce_access(
        {"consent": True},
        "research",
    ) is False
