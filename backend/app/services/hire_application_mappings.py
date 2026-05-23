"""Map employment application JSON to Form I-9 / W-4 prefill payloads."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from ..models import User

_SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
_I9_CITIZENSHIP = frozenset({"citizen", "noncitizen_national", "lawful_permanent_resident", "alien_authorized"})
_W4_FILING = frozenset({"single", "married_joint", "head_of_household"})

_I9_SCALAR_KEYS = (
    "first_name",
    "last_name",
    "middle_initial",
    "other_last_names",
    "address",
    "apt",
    "city",
    "state",
    "zip",
    "date_of_birth",
    "ssn",
    "email",
    "telephone",
    "citizenship_status",
)

_W4_SCALAR_KEYS = (
    "first_name",
    "middle_initial",
    "last_name",
    "address",
    "city",
    "state",
    "zip",
    "ssn",
    "filing_status",
    "dependents_amount",
    "other_income",
    "deductions",
    "extra_withholding",
)


def normalize_ssn(raw: Any) -> str | None:
    if raw is None:
        return None
    s = str(raw).strip().replace(" ", "")
    if not s:
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) != 9:
        return None
    formatted = f"{digits[0:3]}-{digits[3:5]}-{digits[5:9]}"
    if not _SSN_RE.match(formatted):
        return None
    return formatted


def normalize_date_of_birth(raw: Any) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
        return s
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s[:10]


def normalize_citizenship_status(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in _I9_CITIZENSHIP:
        return s
    aliases = {
        "u.s. citizen": "citizen",
        "us citizen": "citizen",
        "united states citizen": "citizen",
        "permanent resident": "lawful_permanent_resident",
        "lawful permanent resident": "lawful_permanent_resident",
        "authorized alien": "alien_authorized",
        "noncitizen national": "noncitizen_national",
    }
    return aliases.get(s, "")


def normalize_filing_status(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in _W4_FILING:
        return s
    aliases = {
        "single": "single",
        "married": "married_joint",
        "married filing jointly": "married_joint",
        "head of household": "head_of_household",
    }
    return aliases.get(s, "")


def _clean_money(raw: Any) -> str:
    s = str(raw or "").strip().replace(",", "").replace("$", "")
    return s


def map_application_to_i9_prefill(user: User, app: dict[str, Any] | None) -> dict[str, Any]:
    app = app or {}
    return {
        "last_name": (user.last_name or "").strip(),
        "first_name": (user.first_name or "").strip(),
        "middle_initial": str(app.get("middle_initial") or "").strip()[:10],
        "other_last_names": "",
        "address": str(app.get("address_line1") or "").strip(),
        "apt": str(app.get("address_line2") or "").strip(),
        "city": str(app.get("city") or "").strip(),
        "state": str(app.get("state") or "").strip(),
        "zip": str(app.get("postal_code") or "").strip(),
        "date_of_birth": normalize_date_of_birth(app.get("date_of_birth")),
        "ssn": normalize_ssn(app.get("ssn")) or "",
        "email": (user.email or "").strip(),
        "telephone": (user.phone or "").strip(),
        "citizenship_status": normalize_citizenship_status(app.get("citizenship_status")),
        "document_choice": "",
        "uscis_a_number": "",
        "admission_i94": "",
        "foreign_passport": "",
        "work_authorization_expiration": "",
        "list_a": {
            "document_type": "",
            "title": "",
            "issuing_authority": "",
            "number": "",
            "expiration": "",
        },
        "list_b": {
            "document_type": "",
            "title": "",
            "issuing_authority": "",
            "number": "",
            "expiration": "",
        },
        "list_c": {
            "document_type": "",
            "title": "",
            "issuing_authority": "",
            "number": "",
            "expiration": "",
        },
    }


def map_application_to_w4_prefill(user: User, app: dict[str, Any] | None) -> dict[str, Any]:
    app = app or {}
    return {
        "first_name": (user.first_name or "").strip(),
        "middle_initial": str(app.get("middle_initial") or "").strip()[:10],
        "last_name": (user.last_name or "").strip(),
        "address": str(app.get("address_line1") or "").strip(),
        "city": str(app.get("city") or "").strip(),
        "state": str(app.get("state") or "").strip(),
        "zip": str(app.get("postal_code") or "").strip(),
        "ssn": normalize_ssn(app.get("ssn")) or "",
        "filing_status": normalize_filing_status(app.get("filing_status")),
        "multiple_jobs": False,
        "higher_withholding": False,
        "dependents_amount": _clean_money(app.get("dependents_amount")),
        "other_income": _clean_money(app.get("other_income")),
        "deductions": _clean_money(app.get("deductions")),
        "extra_withholding": _clean_money(app.get("extra_withholding")),
        "exempt_claim": False,
    }


def _apply_scalar_prefill(target: dict[str, Any], prefill: dict[str, Any], keys: tuple[str, ...]) -> None:
    for key in keys:
        val = prefill.get(key)
        if val is None:
            continue
        if isinstance(val, bool):
            target[key] = val
            continue
        if str(val).strip() != "":
            target[key] = val


def merge_application_into_i9_draft(
    draft: dict[str, Any] | None,
    *,
    user: User,
    app: dict[str, Any] | None,
) -> dict[str, Any]:
    draft = dict(draft or {})
    prefill = map_application_to_i9_prefill(user, app)
    _apply_scalar_prefill(draft, prefill, _I9_SCALAR_KEYS)
    return draft


def merge_application_into_w4_draft(
    draft: dict[str, Any] | None,
    *,
    user: User,
    app: dict[str, Any] | None,
) -> dict[str, Any]:
    draft = dict(draft or {})
    prefill = map_application_to_w4_prefill(user, app)
    _apply_scalar_prefill(draft, prefill, _W4_SCALAR_KEYS)
    for flag in ("multiple_jobs", "higher_withholding", "exempt_claim"):
        if flag in prefill:
            draft[flag] = bool(prefill.get(flag))
    return draft


def sync_i9_w4_drafts_from_application(hire_row, user: User) -> None:
    """Push latest application fields into unsigned I-9 / W-4 drafts."""
    from ..services.hr_i9_crypto import decrypt_section1, encrypt_section1
    from ..services.hr_w4_crypto import decrypt_w4, encrypt_w4

    app = None
    if hire_row.application_json:
        import json

        try:
            parsed = json.loads(hire_row.application_json)
            app = parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            app = None
    if not app:
        return

    if hire_row.i9_signed_at is None:
        i9_draft = None
        if hire_row.i9_section1_json_encrypted:
            try:
                i9_draft = decrypt_section1(hire_row.i9_section1_json_encrypted)
            except ValueError:
                i9_draft = None
        merged_i9 = merge_application_into_i9_draft(i9_draft, user=user, app=app)
        hire_row.i9_section1_json_encrypted = encrypt_section1(merged_i9)

    if hire_row.w4_signed_at is None:
        w4_draft = None
        if hire_row.w4_json_encrypted:
            try:
                w4_draft = decrypt_w4(hire_row.w4_json_encrypted)
            except ValueError:
                w4_draft = None
        merged_w4 = merge_application_into_w4_draft(w4_draft, user=user, app=app)
        hire_row.w4_json_encrypted = encrypt_w4(merged_w4)
