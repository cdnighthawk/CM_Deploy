"""Server-side validation for I-9 Section 1 JSON (employee wizard)."""
from __future__ import annotations

import re
from typing import Any

_CITIZENSHIP = frozenset({"citizen", "noncitizen_national", "lawful_permanent_resident", "alien_authorized"})
_DOC_CHOICE = frozenset({"list_a", "list_b_c"})
_LEGACY_DOC_TYPE = "__legacy__"
_STR_MAX = 500

_LIST_A_DOCUMENTS: dict[str, str] = {
    "us_passport": "U.S. Passport",
    "us_passport_card": "U.S. Passport Card",
    "permanent_resident_card": "Permanent Resident Card or Alien Registration Receipt Card (Form I-551)",
    "foreign_passport_i551": "Foreign passport with temporary I-551 stamp or MRIV notation",
    "ead_i766": "Employment Authorization Document (Form I-766)",
    "foreign_passport_i94": "Foreign passport with Form I-94 or I-94A and work endorsement",
    "fsm_rmi_passport_i94": "Passport from FSM or RMI with Form I-94 or I-94A (Compact of Free Association)",
    "list_a_receipt": "Receipt for replacement of a lost, stolen, or damaged List A document",
    "i94_i551_stamp": "Form I-94 issued to lawful permanent resident with I-551 stamp and photograph",
    "i94_refugee": 'Form I-94 with "RE" notation or refugee stamp',
}

_LIST_B_DOCUMENTS: dict[str, str] = {
    "drivers_license_state": "Driver's license or ID card issued by a U.S. state or outlying possession",
    "govt_id_card": "ID card issued by federal, state, or local government agency",
    "school_id": "School ID card with a photograph",
    "voters_registration": "Voter's registration card",
    "military_card": "U.S. Military card or draft record",
    "military_dependent_id": "Military dependent's ID card",
    "coast_guard_merchant_mariner": "U.S. Coast Guard Merchant Mariner Card",
    "native_american_tribal": "Native American tribal document",
    "canadian_drivers_license": "Driver's license issued by a Canadian government authority",
    "school_record_under18": "School record or report card (under age 18)",
    "clinic_record_under18": "Clinic, doctor, or hospital record (under age 18)",
    "daycare_record_under18": "Day-care or nursery school record (under age 18)",
    "list_b_receipt": "Receipt for replacement of a lost, stolen, or damaged List B document",
}

_LIST_C_DOCUMENTS: dict[str, str] = {
    "ss_card": "U.S. Social Security Card (unrestricted)",
    "birth_cert_report_dos": "Certification of report of birth (Forms DS-1350, FS-545, FS-240)",
    "birth_certificate": "Original or certified copy of U.S. birth certificate with official seal",
    "native_american_tribal_c": "Native American tribal document",
    "form_i197": "U.S. Citizen ID Card (Form I-197)",
    "form_i179": "Identification Card for Use of Resident Citizen in the United States (Form I-179)",
    "dhs_employment_auth": "Employment authorization document issued by the Department of Homeland Security",
    "list_c_receipt": "Receipt for replacement of a lost, stolen, or damaged List C document",
}

_DOC_CATALOG_BY_LIST: dict[str, dict[str, str]] = {
    "list_a": _LIST_A_DOCUMENTS,
    "list_b": _LIST_B_DOCUMENTS,
    "list_c": _LIST_C_DOCUMENTS,
}
_SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _s(val: Any, max_len: int = _STR_MAX) -> str:
    if val is None:
        return ""
    out = str(val).strip()
    if len(out) > max_len:
        return out[:max_len]
    return out


def _require(data: dict[str, Any], key: str, errors: list[str], label: str | None = None) -> str:
    v = _s(data.get(key))
    if not v:
        errors.append(f"{label or key} is required")
    return v


def _resolve_document_type(block: dict[str, Any], catalog: dict[str, str]) -> str:
    dt = _s(block.get("document_type"), 80)
    if dt and dt in catalog:
        return dt
    if dt == _LEGACY_DOC_TYPE:
        return dt
    title = _s(block.get("title")).lower()
    if not title:
        return ""
    for code, label in catalog.items():
        if label.lower() == title:
            return code
    if "passport card" in title:
        return "us_passport_card"
    if "passport" in title and "foreign" not in title:
        return "us_passport"
    if "i-551" in title or "green card" in title or "permanent resident" in title:
        return "permanent_resident_card"
    if "i-766" in title or "employment authorization" in title:
        return "ead_i766"
    if "social security" in title:
        return "ss_card"
    if "driver" in title and "canad" in title:
        return "canadian_drivers_license"
    if "driver" in title:
        return "drivers_license_state"
    if _s(block.get("title")):
        return _LEGACY_DOC_TYPE
    return ""


def _sanitize_doc_block(block: Any, list_key: str) -> dict[str, str]:
    catalog = _DOC_CATALOG_BY_LIST.get(list_key, {})
    out: dict[str, str] = {
        "document_type": "",
        "title": "",
        "issuing_authority": "",
        "number": "",
        "expiration": "",
    }
    if not isinstance(block, dict):
        return out
    out["issuing_authority"] = _s(block.get("issuing_authority"))
    out["number"] = _s(block.get("number"), 80)
    out["expiration"] = _s(block.get("expiration"), 20)
    dt = _resolve_document_type(block, catalog)
    out["document_type"] = dt
    if dt and dt != _LEGACY_DOC_TYPE:
        out["title"] = catalog.get(dt, _s(block.get("title")))
    else:
        out["title"] = _s(block.get("title"))
    return out


def _validate_doc_block(
    block: Any,
    prefix: str,
    errors: list[str],
    *,
    list_key: str,
    require_number: bool = True,
) -> None:
    if not isinstance(block, dict):
        errors.append(f"{prefix}: invalid document block")
        return
    catalog = _DOC_CATALOG_BY_LIST.get(list_key, {})
    sanitized = _sanitize_doc_block(block, list_key)
    block.clear()
    block.update(sanitized)
    dt = sanitized["document_type"]
    if not dt or (dt == _LEGACY_DOC_TYPE and not sanitized["title"]):
        errors.append(f"{prefix}: document type is required")
    if not sanitized["issuing_authority"]:
        errors.append(f"{prefix}: issuing authority is required")
    if require_number and not sanitized["number"]:
        errors.append(f"{prefix}: document number is required")
    if dt and dt not in catalog and dt != _LEGACY_DOC_TYPE:
        errors.append(f"{prefix}: document type is not valid")


def validate_section1(raw: Any) -> tuple[dict[str, Any] | None, list[str]]:
    """Return (sanitized dict, errors). Empty errors means valid."""
    if not isinstance(raw, dict):
        return None, ["section1 must be a JSON object"]
    errors: list[str] = []
    out: dict[str, Any] = {}

    out["last_name"] = _require(raw, "last_name", errors, "Last name")
    out["first_name"] = _require(raw, "first_name", errors, "First name")
    out["middle_initial"] = _s(raw.get("middle_initial"), 10)
    out["other_last_names"] = _s(raw.get("other_last_names"))

    out["address"] = _require(raw, "address", errors, "Street address")
    out["apt"] = _s(raw.get("apt"), 50)
    out["city"] = _require(raw, "city", errors, "City")
    out["state"] = _require(raw, "state", errors, "State")
    out["zip"] = _require(raw, "zip", errors, "ZIP code")

    out["date_of_birth"] = _require(raw, "date_of_birth", errors, "Date of birth")
    if out["date_of_birth"] and not _DATE_RE.match(out["date_of_birth"]):
        errors.append("Date of birth must be YYYY-MM-DD")
    out["ssn"] = _require(raw, "ssn", errors, "Social Security number")
    if out["ssn"] and not _SSN_RE.match(out["ssn"].replace(" ", "")):
        errors.append("Social Security number format is invalid")
    out["email"] = _s(raw.get("email"), 255)
    out["telephone"] = _s(raw.get("telephone"), 50)

    status = _s(raw.get("citizenship_status"))
    if status not in _CITIZENSHIP:
        errors.append("Citizenship / immigration status is required")
    else:
        out["citizenship_status"] = status

    out["uscis_a_number"] = _s(raw.get("uscis_a_number"), 30)
    out["admission_i94"] = _s(raw.get("admission_i94"), 30)
    out["foreign_passport"] = _s(raw.get("foreign_passport"), 80)
    out["work_authorization_expiration"] = _s(raw.get("work_authorization_expiration"), 20)
    if out["work_authorization_expiration"] and not _DATE_RE.match(out["work_authorization_expiration"]):
        errors.append("Work authorization expiration must be YYYY-MM-DD or N/A")

    if status == "lawful_permanent_resident" and not out["uscis_a_number"]:
        errors.append("USCIS A-Number is required for lawful permanent resident")
    if status == "alien_authorized":
        if not out["admission_i94"] and not out["foreign_passport"]:
            errors.append("Admission (I-94) number or foreign passport is required for authorized alien")
        if not out["work_authorization_expiration"]:
            errors.append("Work authorization expiration is required for authorized alien")

    doc_choice = _s(raw.get("document_choice"))
    if doc_choice not in _DOC_CHOICE:
        errors.append("Document choice (List A or List B + C) is required")
    else:
        out["document_choice"] = doc_choice

    list_a = raw.get("list_a")
    list_b = raw.get("list_b")
    list_c = raw.get("list_c")
    if doc_choice == "list_a":
        list_a_dict: dict[str, Any] = dict(list_a) if isinstance(list_a, dict) else {}
        _validate_doc_block(list_a_dict, "List A", errors, list_key="list_a")
        out["list_a"] = list_a_dict
        out["list_b"] = None
        out["list_c"] = None
    elif doc_choice == "list_b_c":
        list_b_dict: dict[str, Any] = dict(list_b) if isinstance(list_b, dict) else {}
        list_c_dict: dict[str, Any] = dict(list_c) if isinstance(list_c, dict) else {}
        _validate_doc_block(list_b_dict, "List B", errors, list_key="list_b")
        _validate_doc_block(list_c_dict, "List C", errors, list_key="list_c")
        out["list_b"] = list_b_dict
        out["list_c"] = list_c_dict
        out["list_a"] = None

    if errors:
        return None, errors
    return out, []
