"""Company-wide cost code catalog and project JCCs seeded from takeoff."""
from __future__ import annotations

import csv
import io
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

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


def _row_get(row: Mapping[str, Any], *keys: str) -> str:
    lower = {str(k).strip().lower(): k for k in row.keys() if k is not None}
    for key in keys:
        src = lower.get(key.lower())
        if src is None:
            continue
        return _blank(row.get(src))
    return ""


def _csi_parts(code: str) -> list[str]:
    return [p for p in _blank(code).replace("-", " ").split() if p]


def _division_key(code: str) -> str:
    parts = _csi_parts(code)
    return parts[0] if parts else ""


def parse_csi_cost_code_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Map CSI MasterFormat Code/Title/Level rows onto company cost-code fields."""
    parsed: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        code = _row_get(row, "code", "costcode", "cost_code")
        title = _row_get(row, "title", "description", "costcodedescription", "name")
        if not code or not title:
            continue
        if code in seen:
            continue
        seen.add(code)
        level_raw = _row_get(row, "level")
        try:
            level = int(level_raw) if level_raw else 0
        except (TypeError, ValueError):
            level = 0
        parsed.append({"code": code, "description": title, "level": level})

    parsed.sort(key=lambda r: r["code"])
    by_code = {r["code"]: r for r in parsed}
    level1 = [r for r in parsed if r["level"] == 1]
    level2 = [r for r in parsed if r["level"] == 2]
    l1_by_div = {_division_key(r["code"]): r for r in level1}
    l2_by_div: dict[str, list[dict[str, Any]]] = {}
    for r in level2:
        l2_by_div.setdefault(_division_key(r["code"]), []).append(r)
    for group in l2_by_div.values():
        group.sort(key=lambda r: r["code"])

    out: list[dict[str, Any]] = []
    for order, r in enumerate(parsed, start=1):
        item: dict[str, Any] = {
            "code": r["code"],
            "description": r["description"],
            "order_number": order,
            "units": "LS",
            "is_active": True,
        }
        div = _division_key(r["code"])
        l1 = l1_by_div.get(div)
        if l1:
            item["division_code"] = l1["code"]
            item["division_desc"] = l1["description"]
        l2 = None
        for cand in l2_by_div.get(div) or []:
            if cand["code"] <= r["code"]:
                l2 = cand
            else:
                break
        if r["level"] >= 2 and l2:
            item["major_code"] = l2["code"]
            item["major_desc"] = l2["description"]
        if r["level"] >= 3:
            parts = _csi_parts(r["code"])
            parent_minor = None
            if len(parts) >= 3 and parts[2] != "00":
                parent_code = f"{parts[0]} {parts[1]} 00"
                parent = by_code.get(parent_code)
                if parent and parent["level"] >= 3 and parent_code != r["code"]:
                    parent_minor = parent
            if parent_minor:
                item["minor_code"] = parent_minor["code"]
                item["minor_desc"] = parent_minor["description"]
                item["subminor_code"] = r["code"]
                item["subminor_desc"] = r["description"]
            else:
                item["minor_code"] = r["code"]
                item["minor_desc"] = r["description"]
        out.append(item)
    return out


def parse_cost_code_csv_text(text: str) -> list[dict[str, Any]]:
    raw = (text or "").lstrip("\ufeff")
    if not raw.strip():
        raise ApiError("csv is empty", 400)
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        raise ApiError("csv is missing a header row", 400)
    items = parse_csi_cost_code_rows(list(reader))
    if not items:
        raise ApiError("csv has no cost code rows", 400)
    return items


def upsert_company_cost_codes(items: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not items:
        raise ApiError("no cost codes to import", 400)
    existing = {r.code: r for r in db.session.scalars(select(CompanyCostCode)).all()}
    created = 0
    updated = 0
    for data in items:
        code = _blank(data.get("code"))
        description = _blank(data.get("description"))
        if not code or not description:
            continue
        row = existing.get(code)
        payload = dict(data)
        for grouping in (
            "division_code",
            "division_desc",
            "major_code",
            "major_desc",
            "minor_code",
            "minor_desc",
            "subminor_code",
            "subminor_desc",
        ):
            payload.setdefault(grouping, None)
        if row is None:
            row = CompanyCostCode(id=uuid.uuid4(), code=code, description=description, units="LS")
            db.session.add(row)
            existing[code] = row
            created += 1
        else:
            updated += 1
            if row.units:
                payload.pop("units", None)
        _apply_cost_code_fields(row, payload)
        row.code = code
        row.description = description
        row.is_active = True
        if not row.units:
            row.units = "LS"
    db.session.commit()
    return {
        "created": created,
        "updated": updated,
        "total": created + updated,
        "entity": "company_cost_codes",
    }


def import_company_cost_codes(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return upsert_company_cost_codes(parse_csi_cost_code_rows(rows))


def import_company_cost_codes_csv(text: str) -> dict[str, Any]:
    return upsert_company_cost_codes(parse_cost_code_csv_text(text))


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
