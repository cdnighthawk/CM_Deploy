"""Server-side validation for Form W-4 JSON (employee hire wizard)."""
from __future__ import annotations

import re
from typing import Any

_FILING_STATUS = frozenset({"single", "married_joint", "head_of_household"})
_SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
_MONEY_RE = re.compile(r"^\d+(\.\d{1,2})?$")
_STR_MAX = 500


def _s(val: Any, max_len: int = _STR_MAX) -> str:
    if val is None:
        return ""
    out = str(val).strip()
    if len(out) > max_len:
        return out[:max_len]
    return out


def _bool(val: Any) -> bool:
    if val is True or val is False:
        return val
    if isinstance(val, str):
        return val.strip().lower() in ("true", "1", "yes", "on")
    return bool(val)


def _money(val: Any, field: str, errors: list[str]) -> str:
    s = _s(val, 32)
    if not s:
        return ""
    cleaned = s.replace(",", "").replace("$", "")
    if not _MONEY_RE.match(cleaned):
        errors.append(f"{field} must be a dollar amount (e.g. 0 or 1500.00)")
        return s
    return cleaned


def validate_w4(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (sanitized dict, errors). Empty errors means valid."""
    if not isinstance(raw, dict):
        return None, ["w4 must be a JSON object"]
    errors: list[str] = []
    out: dict[str, Any] = {}

    out["first_name"] = _s(raw.get("first_name"))
    if not out["first_name"]:
        errors.append("First name is required")
    out["middle_initial"] = _s(raw.get("middle_initial"), 10)
    out["last_name"] = _s(raw.get("last_name"))
    if not out["last_name"]:
        errors.append("Last name is required")

    out["address"] = _s(raw.get("address"))
    if not out["address"]:
        errors.append("Address is required")
    out["city"] = _s(raw.get("city"))
    if not out["city"]:
        errors.append("City is required")
    out["state"] = _s(raw.get("state"), 30)
    if not out["state"]:
        errors.append("State is required")
    out["zip"] = _s(raw.get("zip"), 20)
    if not out["zip"]:
        errors.append("ZIP code is required")

    out["ssn"] = _s(raw.get("ssn"), 20)
    if not out["ssn"]:
        errors.append("Social Security number is required")
    elif not _SSN_RE.match(out["ssn"].replace(" ", "")):
        errors.append("Social Security number format is invalid")

    status = _s(raw.get("filing_status"), 40)
    if status not in _FILING_STATUS:
        errors.append("Filing status is required")
    else:
        out["filing_status"] = status

    out["multiple_jobs"] = _bool(raw.get("multiple_jobs"))
    out["higher_withholding"] = _bool(raw.get("higher_withholding"))
    out["dependents_amount"] = _money(raw.get("dependents_amount"), "Dependents amount", errors)
    out["other_income"] = _money(raw.get("other_income"), "Other income", errors)
    out["deductions"] = _money(raw.get("deductions"), "Deductions", errors)
    out["extra_withholding"] = _money(raw.get("extra_withholding"), "Extra withholding", errors)
    out["exempt_claim"] = _bool(raw.get("exempt_claim"))

    if out["exempt_claim"]:
        if out["dependents_amount"] or out["other_income"] or out["deductions"] or out["extra_withholding"]:
            errors.append("Exempt claim cannot be combined with withholding amounts on Steps 3–4")
        if out["multiple_jobs"] or out["higher_withholding"]:
            errors.append("Exempt claim cannot be combined with multiple jobs or higher withholding checkboxes")

    if errors:
        return None, errors
    return out, []
