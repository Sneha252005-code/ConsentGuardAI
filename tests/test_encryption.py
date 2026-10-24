import pytest
from security.encryption import (
    encrypt_data,
    decrypt_data,
    EncryptionError,
)


def test_encrypt_decrypt_round_trip():
    original = "test data"
    encrypted = encrypt_data(original)

    assert encrypted != original
    assert decrypt_data(encrypted) == original


def test_decryption_rejects_invalid_ciphertext():
    with pytest.raises(EncryptionError):
        decrypt_data("invalid-ciphertext")