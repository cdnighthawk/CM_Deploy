"""Fernet encrypt/decrypt for W-4 JSON (SSN)."""
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


def encrypt_w4(w4: dict[str, Any]) -> str:
    payload = json.dumps(w4, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return _fernet().encrypt(payload).decode("ascii")


def decrypt_w4(blob: str) -> dict[str, Any]:
    try:
        raw = _fernet().decrypt(blob.encode("ascii"))
    except InvalidToken as exc:
        raise ValueError("invalid or corrupted W-4 ciphertext") from exc
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("W-4 payload must be a JSON object")
    return data
