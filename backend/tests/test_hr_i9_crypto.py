"""Unit tests for I-9 Section 1 Fernet helpers."""
from __future__ import annotations

import pytest

from app.services.hr_i9_crypto import decrypt_section1, encrypt_section1


def test_encrypt_decrypt_roundtrip(flask_app):
    with flask_app.app_context():
        payload = {
            "last_name": "Test",
            "first_name": "User",
            "ssn": "123-45-6789",
            "citizenship_status": "citizen",
        }
        blob = encrypt_section1(payload)
        assert isinstance(blob, str)
        assert decrypt_section1(blob) == payload


def test_decrypt_invalid_blob(flask_app):
    with flask_app.app_context():
        with pytest.raises(ValueError, match="invalid or corrupted"):
            decrypt_section1("not-valid-ciphertext")
