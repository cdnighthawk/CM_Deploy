"""Unit tests for W-4 Fernet helpers."""
from __future__ import annotations

import pytest

from app.services.hr_w4_crypto import decrypt_w4, encrypt_w4


def test_encrypt_decrypt_roundtrip(flask_app):
    with flask_app.app_context():
        payload = {
            "first_name": "Jamie",
            "last_name": "Rivera",
            "ssn": "123-45-6789",
            "filing_status": "single",
        }
        blob = encrypt_w4(payload)
        assert isinstance(blob, str)
        assert decrypt_w4(blob) == payload


def test_decrypt_invalid_blob(flask_app):
    with flask_app.app_context():
        with pytest.raises(ValueError, match="invalid or corrupted"):
            decrypt_w4("not-valid-ciphertext")
