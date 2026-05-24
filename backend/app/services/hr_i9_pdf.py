"""Fill the official USCIS Form I-9 PDF (Section 1) and overlay employee signature."""
from __future__ import annotations

import base64
import io
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import fitz
from flask import current_app

from ..models import User

_CITIZENSHIP_CB = {
    "citizen": "CB_1",
    "noncitizen_national": "CB_2",
    "lawful_permanent_resident": "CB_3",
    "alien_authorized": "CB_4",
}

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def i9_template_path() -> Path:
    path = Path(current_app.root_path) / "static" / "forms" / "uscis-i-9.pdf"
    if not path.is_file():
        raise FileNotFoundError(f"USCIS I-9 template not found at {path}")
    return path


def _mmddyyyy(raw: str | None) -> str:
    val = (raw or "").strip()
    if not val:
        return ""
    if val.upper() == "N/A":
        return "N/A"
    if _ISO_DATE.match(val):
        y, m, d = val.split("-")
        return f"{m}/{d}/{y}"
    return val


def _today_mmddyyyy(when: datetime | None = None) -> str:
    dt = when or datetime.now(timezone.utc)
    return dt.strftime("%m/%d/%Y")


def _decode_signature_png(data_url: str | None) -> bytes | None:
    if not data_url:
        return None
    raw = data_url.strip()
    if raw.startswith("data:"):
        parts = raw.split(",", 1)
        if len(parts) != 2:
            return None
        raw = parts[1]
    try:
        payload = base64.b64decode(raw)
    except Exception:
        return None
    return payload if payload else None


def _doc_block(section1: dict[str, Any], key: str) -> dict[str, Any]:
    block = section1.get(key)
    return block if isinstance(block, dict) else {}


def section1_to_pdf_fields(section1: dict[str, Any], *, user: User | None = None) -> dict[str, str]:
    """Map validated Section 1 JSON to USCIS I-9 AcroForm field names."""
    email = (section1.get("email") or "").strip() or ((user.email or "").strip() if user else "")
    fields: dict[str, str] = {
        "Last Name (Family Name)": str(section1.get("last_name") or "").strip(),
        "First Name Given Name": str(section1.get("first_name") or "").strip(),
        "Employee Middle Initial (if any)": str(section1.get("middle_initial") or "").strip(),
        "Employee Other Last Names Used (if any)": str(section1.get("other_last_names") or "").strip(),
        "Address Street Number and Name": str(section1.get("address") or "").strip(),
        "Apt Number (if any)": str(section1.get("apt") or "").strip(),
        "City or Town": str(section1.get("city") or "").strip(),
        "State": str(section1.get("state") or "").strip(),
        "ZIP Code": str(section1.get("zip") or "").strip(),
        "Date of Birth mmddyyyy": _mmddyyyy(str(section1.get("date_of_birth") or "")),
        "US Social Security Number": str(section1.get("ssn") or "").strip(),
        "Employees E-mail Address": email,
        "Telephone Number": str(section1.get("telephone") or "").strip(),
    }

    status = str(section1.get("citizenship_status") or "").strip()
    if status == "lawful_permanent_resident":
        a_num = str(section1.get("uscis_a_number") or "").strip()
        fields["3 A lawful permanent resident Enter USCIS or ANumber"] = a_num
        fields["USCIS ANumber"] = a_num
    elif status == "alien_authorized":
        fields["Form I94 Admission Number"] = str(section1.get("admission_i94") or "").strip()
        fields["Foreign Passport Number and Country of IssuanceRow1"] = str(
            section1.get("foreign_passport") or ""
        ).strip()
        fields["Exp Date mmddyyyy"] = _mmddyyyy(str(section1.get("work_authorization_expiration") or ""))

    doc_choice = str(section1.get("document_choice") or "").strip()
    if doc_choice == "list_a":
        doc = _doc_block(section1, "list_a")
        fields["Document Title 0"] = str(doc.get("title") or "").strip()
        fields["Issuing Authority 1"] = str(doc.get("issuing_authority") or "").strip()
        fields["Document Number 0 (if any)"] = str(doc.get("number") or "").strip()
        fields["Expiration Date 0"] = _mmddyyyy(str(doc.get("expiration") or ""))
    elif doc_choice == "list_b_c":
        doc_b = _doc_block(section1, "list_b")
        doc_c = _doc_block(section1, "list_c")
        fields["List B Document 1 Title"] = str(doc_b.get("title") or "").strip()
        fields["List B Issuing Authority 1"] = str(doc_b.get("issuing_authority") or "").strip()
        fields["List B Document Number 1"] = str(doc_b.get("number") or "").strip()
        fields["List B Expiration Date 1"] = _mmddyyyy(str(doc_b.get("expiration") or ""))
        fields["List C Document Title 1"] = str(doc_c.get("title") or "").strip()
        fields["List C Issuing Authority 1"] = str(doc_c.get("issuing_authority") or "").strip()
        fields["List C Document Number 1"] = str(doc_c.get("number") or "").strip()
        fields["List C Expiration Date 1"] = _mmddyyyy(str(doc_c.get("expiration") or ""))

    return {k: v for k, v in fields.items() if v}


def render_i9_pdf_bytes(
    *,
    section1: dict[str, Any],
    user: User | None = None,
    signature_png: str | None = None,
    signed_at: datetime | None = None,
    typed_full_name: str | None = None,
) -> bytes:
    """Return a filled USCIS I-9 PDF (Section 1). Signature image is overlaid when provided."""
    template = i9_template_path()
    doc = fitz.open(str(template))
    page = doc[0]
    values = section1_to_pdf_fields(section1, user=user)
    cb_name = _CITIZENSHIP_CB.get(str(section1.get("citizenship_status") or "").strip())
    sig_rect: fitz.Rect | None = None
    date_field = "Today's Date mmddyyy"

    for widget in page.widgets() or []:
        name = widget.field_name or ""
        if name in values:
            widget.field_value = values[name]
            widget.update()
        elif name == cb_name:
            widget.field_value = True
            widget.update()
        elif name == "Signature of Employee":
            sig_rect = widget.rect
            if typed_full_name and not signature_png:
                widget.field_value = typed_full_name
                widget.update()
        elif name == date_field and signed_at is not None:
            widget.field_value = _today_mmddyyyy(signed_at)
            widget.update()

    png = _decode_signature_png(signature_png)
    if png and sig_rect is not None:
        page.insert_image(sig_rect, stream=png, keep_proportion=True, overlay=True)

    buf = io.BytesIO()
    doc.save(buf, deflate=True, garbage=4)
    doc.close()
    return buf.getvalue()
