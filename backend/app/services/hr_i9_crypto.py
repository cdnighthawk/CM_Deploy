"""Fernet encrypt/decrypt for I-9 Section 1 JSON (SSN, document numbers)."""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


def _fernet() -> Fernet:
    raw = (current_app.config.get("TOKEN_ENCRYPTION_KEY") or "").strip()
    if raw:
        seed = raw
    else:
        seed = str(current_app.config.get("SECRET_KEY") or "dev")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest())
    return Fernet(key)


def encrypt_section1(section1: dict[str, Any]) -> str:
    payload = json.dumps(section1, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")


def decrypt_section1(blob: str) -> dict[str, Any]:
    try:
        raw = _fernet().decrypt(blob.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("invalid or corrupted I-9 ciphertext") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("I-9 payload must be a JSON object")
    return data
