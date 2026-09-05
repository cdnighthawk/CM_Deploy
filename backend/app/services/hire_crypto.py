"""App-level Fernet encryption for hire-packet PII (SSN, DOB, bank).

Key source: ``TOKEN_ENCRYPTION_KEY`` (preferred) or ``SECRET_KEY`` SHA-256
derived into a urlsafe Fernet key (same scheme as I-9/W-4 crypto).

Key rotation
------------
1. Keep the current key until every ciphertext is rewritten.
2. Decrypt SSN/DOB/routing/account/FEIN/EDD with the old key.
3. Set the new ``TOKEN_ENCRYPTION_KEY`` in the environment.
4. Re-encrypt and save each ``HirePerson``, ``HireDirectDeposit``, and secret
   ``HireCompanySetting`` row.
5. Discard the old key only after a verified round-trip on a sample packet.

IT: database backups of ciphertext without this key are unreadable. Store the
key in a secrets manager, never next to the dump. Do not put hire PII in
ChatBot, Grok, ``aiReviewBus``, or time-card CSVs.
"""
from __future__ import annotations

import base64
import hashlib
import re

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app

_DIGITS = re.compile(r"\D+")


def _fernet() -> Fernet:
    raw = (current_app.config.get("TOKEN_ENCRYPTION_KEY") or "").strip()
    seed = raw if raw else str(current_app.config.get("SECRET_KEY") or "dev")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest())
    return Fernet(key)


def encrypt_str(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text == "":
        return None
    return _fernet().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt_str(blob: str | None) -> str | None:
    if not blob:
        return None
    try:
        return _fernet().decrypt(blob.encode("ascii")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("invalid or corrupted hire ciphertext") from exc


def digits_only(value: str | None) -> str:
    return _DIGITS.sub("", value or "")


def last4(value: str | None) -> str | None:
    digits = digits_only(value)
    if len(digits) < 4:
        return digits or None
    return digits[-4:]


def hash_token(raw: str) -> str:
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()
