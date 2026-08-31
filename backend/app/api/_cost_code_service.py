"""Company-wide cost code catalog and project JCCs seeded from takeoff."""
from __future__ import annotations

import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError

from ..extensions import db
from ..models import CompanyCostCode, CostCode, Estimate, LeadEstimate, TakeoffLineItem
from ._rfi_service import ApiError, _apply_cost_code_fields, lookup_public

_MASTER_COPY = (
    "description",
    "order_number",
    "units",
    "owner_cost_code",
    "owner_cost_code_desc",
    "default_tax_code",
    "division_code",
    "division_desc",
    "major_code",
    "major_desc",
    "minor_code",
    "minor_desc",
    "subminor_code",
    "subminor_desc",
    "workers_comp_code",
    "ap_tax_code",
    "ar_tax_code",
)


def _blank(v: Any) -> str:
    return str(v or "").strip()


def company_cost_code_public(row: CompanyCostCode) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "code": row.code,
        "description": row.description,
        "is_active": bool(row.is_active),
        "order_number": int(row.order_number or 0),
        "units": row.units,
    }
    for attr in _MASTER_COPY:
        if attr in ("description", "order_number", "units"):
            continue
        out[attr] = getattr(row, attr, None)
    return out


def list_company_cost_codes(*, active_only: bool = False) -> dict[str, Any]:
    q = select(CompanyCostCode).order_by(CompanyCostCode.order_number.asc(), CompanyCostCode.code.asc())
    if active_only:
        q = q.where(CompanyCostCode.is_active.is_(True))
    rows = db.session.scalars(q).all()
    return {"items": [company_cost_code_public(r) for r in rows], "entity": "company_cost_codes"}


def get_company_cost_code_by_code(code: str) -> CompanyCostCode | None:
    c = _blank(code)
    if not c:
        return None
    return db.session.scalar(select(CompanyCostCode).where(CompanyCostCode.code == c))


def create_company_cost_code(data: Mapping[str, Any]) -> dict[str, Any]:
    code = _blank(data.get("code"))
    description = _blank(data.get("description"))
    if not code:
        raise ApiError("code is required", 400)
    if not description:
        raise ApiError("description is required", 400)
    row = CompanyCostCode(id=uuid.uuid4(), code=code, description=description)
    _apply_cost_code_fields(row, data)
    row.code = code
    row.description = description
    if not row.units:
        row.units = "LS"
    db.session.add(row)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError("that cost code already exists", 409) from exc
    return company_cost_code_public(row)


def patch_company_cost_code(row_id: uuid.UUID, data: Mapping[str, Any]) -> dict[str, Any]:
    row = db.session.get(CompanyCostCode, row_id)
    if row is None:
        raise ApiError("cost code not found", 404)
    if "code" in data:
        code = _blank(data.get("code"))
        if not code:
            raise ApiError("code is required", 400)
    if "description" in data:
        description = _blank(data.get("description"))
        if not description:
            raise ApiError("description is required", 400)
    _apply_cost_code_fields(row, data)
    try:
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        raise ApiError("that cost code already exists", 409) from exc
    return company_cost_code_public(row)


def delete_company_cost_code(row_id: uuid.UUID) -> dict[str, Any]:
    row = db.session.get(CompanyCostCode, row_id)
    if row is None:
        raise ApiError("cost code not found", 404)
    db.session.delete(row)
    db.session.commit()
    return {"ok": True, "id": str(row_id), "entity": "company_cost_codes"}


def project_takeoff_filter(project_id: uuid.UUID):
    lead_ids = select(LeadEstimate.id).where(LeadEstimate.project_id == project_id)
    est_ids = select(Estimate.id).where(Estimate.project_id == project_id)
    return or_(
        TakeoffLineItem.project_id == project_id,
        TakeoffLineItem.lead_estimate_id.in_(lead_ids),
        TakeoffLineItem.estimate_id.in_(est_ids),
    )


def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def sync_project_cost_codes_from_takeoff(project_id: uuid.UUID) -> list[dict[str, Any]]:
    lines = db.session.scalars(select(TakeoffLineItem).where(project_takeoff_filter(project_id))).all()
    grouped: dict[str, dict[str, Any]] = {}
    for line in lines:
        code = _blank(line.job_cost_code)
        if not code:
            continue
        bucket = grouped.setdefault(
            code,
            {"quantity": Decimal("0"), "units": _blank(line.unit), "description": _blank(line.job_cost_code_description), "lines": 0},
        )
        bucket["quantity"] += _dec(line.quantity)
        bucket["lines"] += 1
        if not bucket["units"] and _blank(line.unit):
            bucket["units"] = _blank(line.unit)
        if not bucket["description"] and _blank(line.job_cost_code_description):
            bucket["description"] = _blank(line.job_cost_code_description)

    existing = {
        r.code: r
        for r in db.session.scalars(select(CostCode).where(CostCode.project_id == project_id)).all()
    }
    masters = {r.code: r for r in db.session.scalars(select(CompanyCostCode)).all()}

    seen: set[str] = set()
    for code, agg in grouped.items():
        seen.add(code)
        master = masters.get(code)
        row = existing.get(code)
        if row is None:
            row = CostCode(project_id=project_id, code=code)
            db.session.add(row)
            existing[code] = row
        row.code = code
        row.is_active = True
        row.quantity = agg["quantity"]
        if master:
            for attr in _MASTER_COPY:
                setattr(row, attr, getattr(master, attr))
            if not row.units:
                row.units = agg["units"] or "LS"
        else:
            row.description = agg["description"] or code
            row.units = agg["units"] or row.units or "LS"
            if not row.order_number:
                row.order_number = 0

    for code, row in existing.items():
        if code not in seen:
            row.is_active = False

    db.session.commit()
    active = [r for r in existing.values() if r.is_active]
    active.sort(key=lambda r: (r.order_number or 0, r.code or ""))
    out = []
    for r in active:
        item = lookup_public(r)
        item["takeoff_line_count"] = grouped.get(r.code, {}).get("lines", 0)
        item["in_company_list"] = r.code in masters
        out.append(item)
    return out
