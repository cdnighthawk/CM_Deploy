"""Project read/update for Job info tab."""
from __future__ import annotations

import re
import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select

from ..extensions import db
from ..models import Project

PROJECT_STATUSES = frozenset(
    {"planning", "active", "on_hold", "complete", "archived", "cancelled"}
)
PROJECT_TYPES = frozenset({"commercial", "government", "residential", "mixed", "other"})


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date):
        return raw
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError as e:
        raise ApiError(f"invalid date: {s}") from e


def _parse_decimal(raw: Any, field: str) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError) as e:
        raise ApiError(f"invalid {field}") from e


def _normalize_emails(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, list):
        parts = [str(x).strip() for x in raw if str(x).strip()]
    else:
        parts = [p.strip() for p in re.split(r"[,;\s]+", str(raw)) if p.strip()]
    if not parts:
        return None
    email_re = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    for em in parts:
        if not email_re.match(em):
            raise ApiError(f"invalid email address: {em}")
    return ", ".join(parts)


def patch_project(project_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ApiError("JSON body required")
    p = db.session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        return None

    if "name" in data:
        name = str(data.get("name") or "").strip()
        if not name:
            raise ApiError("name cannot be empty")
        p.name = name[:255]
    if "number" in data:
        num = data.get("number")
        p.number = None if num is None or str(num).strip() == "" else str(num).strip()[:50]
    if "description" in data:
        d = data.get("description")
        p.description = None if d is None else (str(d).strip() or None)
    if "notes" in data:
        n = data.get("notes")
        p.notes = None if n is None else (str(n).strip() or None)
    if "status" in data:
        st = str(data.get("status") or "").strip().lower()
        if st not in PROJECT_STATUSES:
            raise ApiError("invalid status")
        p.status = st
    if "project_type" in data:
        pt = str(data.get("project_type") or "").strip().lower()
        if pt not in PROJECT_TYPES:
            raise ApiError("invalid project_type")
        p.project_type = pt
    for key, attr, maxlen in (
        ("address_line1", "address_line1", 255),
        ("address_line2", "address_line2", 255),
        ("city", "city", 120),
        ("state", "state", 50),
        ("postal_code", "postal_code", 20),
    ):
        if key in data:
            v = data.get(key)
            setattr(p, attr, None if v is None else (str(v).strip()[:maxlen] or None))
    if "country" in data:
        c = data.get("country")
        p.country = None if c is None else (str(c).strip()[:2].upper() or None)
    if "contract_value" in data:
        dec = _parse_decimal(data.get("contract_value"), "contract_value")
        p.contract_value = float(dec) if dec is not None else None
    if "contract_date" in data:
        p.contract_date = _parse_date(data.get("contract_date"))
    if "start_date" in data:
        p.start_date = _parse_date(data.get("start_date"))
    if "substantial_completion_date" in data:
        p.substantial_completion_date = _parse_date(data.get("substantial_completion_date"))
    if "closeout_date" in data:
        p.closeout_date = _parse_date(data.get("closeout_date"))
    if "retention_percentage" in data:
        dec = _parse_decimal(data.get("retention_percentage"), "retention_percentage")
        p.retention_percentage = float(dec) if dec is not None else None
    if "prevailing_wage" in data:
        if not isinstance(data["prevailing_wage"], bool):
            raise ApiError("prevailing_wage must be boolean")
        p.prevailing_wage = data["prevailing_wage"]
    if "dbe_required" in data:
        if not isinstance(data["dbe_required"], bool):
            raise ApiError("dbe_required must be boolean")
        p.dbe_required = data["dbe_required"]
    if "sage_project_id" in data:
        s = data.get("sage_project_id")
        p.sage_project_id = None if s is None else (str(s).strip()[:100] or None)
    if "textura_project_id" in data:
        t = data.get("textura_project_id")
        p.textura_project_id = None if t is None else (str(t).strip()[:64] or None)

    if "invoice_method" in data:
        method = data.get("invoice_method")
        p.invoice_method = None if method is None or str(method).strip() == "" else str(method).strip()[:80]
    if "invoice_due_date" in data:
        p.invoice_due_date = _parse_date(data.get("invoice_due_date"))
    if "invoice_recipient_emails" in data:
        p.invoice_recipient_emails = _normalize_emails(data.get("invoice_recipient_emails"))

    method_code = (p.invoice_method or "").strip().lower()
    if method_code == "email":
        if not (p.invoice_recipient_emails or "").strip():
            raise ApiError("invoice_recipient_emails required when invoice method is Email")
    elif method_code and method_code not in ("textura", "email"):
        from ..models import InvoiceDeliveryMethod

        exists = db.session.scalar(
            select(InvoiceDeliveryMethod.id).where(InvoiceDeliveryMethod.code == method_code)
        )
        if exists is None:
            raise ApiError("unknown invoice_method code")

    db.session.flush()
    db.session.refresh(p)
    from .v1 import _project_detail_public

    return _project_detail_public(p)
