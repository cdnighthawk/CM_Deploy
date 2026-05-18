"""Invoice delivery method catalog (Textura, Email, custom)."""
from __future__ import annotations

import re
import uuid
from typing import Any

from sqlalchemy import select

from ..extensions import db
from ..models import InvoiceDeliveryMethod


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _slug_code(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return (s[:72] or "method")


def method_public(m: InvoiceDeliveryMethod) -> dict[str, Any]:
    return {
        "id": str(m.id),
        "code": m.code,
        "label": m.label,
        "is_system": m.is_system,
    }


def list_methods() -> list[dict[str, Any]]:
    rows = db.session.scalars(
        select(InvoiceDeliveryMethod).order_by(
            InvoiceDeliveryMethod.is_system.desc(),
            InvoiceDeliveryMethod.label.asc(),
        )
    ).all()
    return [method_public(m) for m in rows]


def create_method(data: dict[str, Any]) -> dict[str, Any]:
    label = str(data.get("label") or "").strip()
    if not label:
        raise ApiError("label is required")
    if len(label) > 120:
        raise ApiError("label is too long")
    code = str(data.get("code") or "").strip().lower() or _slug_code(label)
    if not re.match(r"^[a-z][a-z0-9_]{0,79}$", code):
        raise ApiError("code must be lowercase letters, digits, and underscores")
    if code in ("textura", "email"):
        raise ApiError("reserved code; use built-in Textura or Email")
    base = code
    n = 2
    while db.session.scalar(select(InvoiceDeliveryMethod.id).where(InvoiceDeliveryMethod.code == code)) is not None:
        code = f"{base}_{n}"[:80]
        n += 1
    m = InvoiceDeliveryMethod(code=code, label=label, is_system=False)
    db.session.add(m)
    db.session.flush()
    return method_public(m)


def label_for_code(code: str | None) -> str | None:
    if not code:
        return None
    row = db.session.scalar(select(InvoiceDeliveryMethod).where(InvoiceDeliveryMethod.code == code))
    return row.label if row else code.replace("_", " ").title()
