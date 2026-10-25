
import pytest

from security.authentication import (
    hash_password,
    verify_password,
    password_hash_needs_update,
)


def test_password_is_hashed():
    password = "StrongPassword123!"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(hashed, password)


def test_wrong_password_is_rejected():
    hashed = hash_password("StrongPassword123!")

    assert not verify_password(hashed, "WrongPassword123!")


def test_different_hashes_for_same_password():
    password = "StrongPassword123!"

    first_hash = hash_password(password)
    second_hash = hash_password(password)

    assert first_hash != second_hash
    assert verify_password(first_hash, password)
    assert verify_password(second_hash, password)


def test_short_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password("short")


def test_non_string_password_is_rejected():
    with pytest.raises(ValueError):
        hash_password(None)


def test_invalid_hash_returns_false():
    assert not verify_password("invalid-hash", "StrongPassword123!")


def test_rehash_check_handles_invalid_hash():
    assert not password_hash_needs_update("invalid-hash")
