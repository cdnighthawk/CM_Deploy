"""Project-scoped commitments (PO / subcontract) API logic."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Commitment, CommitmentBillAllocation, CommitmentLineItem, Company, CostCode, Rfp
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

COMMITMENT_KINDS = frozenset({"purchase_order", "subcontract"})
COMMITMENT_STATUSES = frozenset(
    {"draft", "pending_submission", "pending", "not_approved", "approved"}
)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


def _dec(v: Any) -> Decimal | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    s = str(raw).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _parse_dt(raw: Any) -> datetime | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = str(raw).strip()
    if not s:
        return None
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except ValueError:
        return None


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _is_writer(cu: CurrentUser) -> bool:
    return _is_admin(cu) or cu.has_role("standard")


def _can_view(cu: CurrentUser) -> bool:
    return _is_admin(cu) or _is_writer(cu) or cu.has_role("read_only", "readonly")


def _can_mutate(cu: CurrentUser) -> bool:
    return _is_admin(cu) or _is_writer(cu)


def _commitment_blocked_for(c: Commitment, cu: CurrentUser) -> bool:
    if not c.workflow_rule_active:
        return False
    return not _is_admin(cu)


def _vendor_company_ok(c: Company) -> bool:
    return c.company_type in ("vendor", "subcontractor", "gc", "other", "self")


def _serialize_line(li: CommitmentLineItem) -> dict[str, Any]:
    return {
        "id": str(li.id),
        "commitment_id": str(li.commitment_id),
        "cost_code_id": str(li.cost_code_id) if li.cost_code_id else None,
        "sort_order": li.sort_order,
        "description": li.description,
        "quantity": str(li.quantity),
        "unit": li.unit,
        "unit_cost": str(li.unit_cost),
        "line_total": str(li.line_total),
        "tax_code": li.tax_code,
        "takeoff_line_item_id": str(li.takeoff_line_item_id) if li.takeoff_line_item_id else None,
        "created_at": _iso(li.created_at),
        "updated_at": _iso(li.updated_at),
    }


def _serialize_bill(b: CommitmentBillAllocation) -> dict[str, Any]:
    return {
        "id": str(b.id),
        "commitment_id": str(b.commitment_id),
        "vendor_bill_ref": b.vendor_bill_ref,
        "allocated_amount": str(b.allocated_amount),
        "billed_at": _iso(b.billed_at) if b.billed_at else None,
        "notes": b.notes,
        "created_at": _iso(b.created_at),
        "updated_at": _iso(b.updated_at),
    }


def _serialize_commitment_row(c: Commitment, vendor_name: str, rfp: Rfp | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": str(c.id),
        "project_id": str(c.project_id),
        "vendor_company_id": str(c.vendor_company_id),
        "vendor_name": vendor_name,
        "commitment_kind": c.commitment_kind,
        "reference_number": c.reference_number,
        "title": c.title,
        "status": c.status,
        "status_effective_date": _iso(c.status_effective_date) if c.status_effective_date else None,
        "approved_at": _iso(c.approved_at),
        "workflow_rule_active": c.workflow_rule_active,
        "retention_percentage": str(c.retention_percentage) if c.retention_percentage is not None else None,
        "currency": c.currency,
        "total_amount": str(c.total_amount) if c.total_amount is not None else None,
        "rfp_id": str(c.rfp_id) if c.rfp_id else None,
        "notes": c.notes,
        "created_at": _iso(c.created_at),
        "updated_at": _iso(c.updated_at),
    }
    if c.rfp_id:
        row["rfp_title"] = rfp.title if rfp is not None else None
        row["rfp_status"] = rfp.status if rfp is not None else None
    return row


def _load_commitment(project_id: uuid.UUID, commitment_id: uuid.UUID) -> Commitment | None:
    stmt = (
        select(Commitment)
        .where(Commitment.id == commitment_id, Commitment.project_id == project_id)
        .options(
            selectinload(Commitment.line_items),
            selectinload(Commitment.bill_allocations),
        )
    )
    return db.session.scalars(stmt).first()


def list_commitments(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    stmt = (
        select(Commitment, Company.name)
        .join(Company, Company.id == Commitment.vendor_company_id)
        .where(Commitment.project_id == project_id, Company.deleted_at.is_(None))
        .order_by(Commitment.created_at.desc())
    )
    rows = db.session.execute(stmt).all()
    rfp_ids = {c.rfp_id for c, _ in rows if c.rfp_id}
    rfp_map: dict[uuid.UUID, Rfp] = {}
    if rfp_ids:
        loaded = db.session.scalars(select(Rfp).where(Rfp.id.in_(rfp_ids))).all()
        rfp_map = {r.id: r for r in loaded}
    items = [
        _serialize_commitment_row(c, name, rfp_map.get(c.rfp_id) if c.rfp_id else None) for c, name in rows
    ]
    return {"items": items, "entity": "commitments"}


def get_commitment_detail(project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    vendor = db.session.get(Company, c.vendor_company_id)
    vendor_name = vendor.name if vendor else ""
    linked_rfp = db.session.get(Rfp, c.rfp_id) if c.rfp_id else None
    item = _serialize_commitment_row(c, vendor_name, linked_rfp)
    lines = sorted(c.line_items, key=lambda x: (x.sort_order, str(x.id)))
    bills = sorted(c.bill_allocations, key=lambda x: str(x.created_at))
    return {
        "item": item,
        "line_items": [_serialize_line(li) for li in lines],
        "bill_allocations": [_serialize_bill(b) for b in bills],
        "permissions": {
            "can_edit": _can_mutate(cu) and not _commitment_blocked_for(c, cu),
            "can_delete": _can_mutate(cu) and not _commitment_blocked_for(c, cu),
            "can_add_lines": _can_mutate(cu) and not _commitment_blocked_for(c, cu),
            "can_add_bills": _can_mutate(cu) and not _commitment_blocked_for(c, cu),
        },
    }


def create_commitment(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    kind = (data.get("commitment_kind") or data.get("kind") or "").strip()
    if kind not in COMMITMENT_KINDS:
        raise ApiError("commitment_kind must be purchase_order or subcontract", 400)
    vid = _parse_uuid(data.get("vendor_company_id"))
    if vid is None:
        raise ApiError("vendor_company_id required", 400)
    vendor = db.session.get(Company, vid)
    if vendor is None or vendor.deleted_at is not None:
        raise ApiError("vendor company not found", 400)
    if not _vendor_company_ok(vendor):
        raise ApiError("invalid vendor company type for procurement", 400)
    rfp_id = _parse_uuid(data.get("rfp_id"))
    if rfp_id is not None:
        rfp = db.session.get(Rfp, rfp_id)
        if rfp is None:
            raise ApiError("rfp not found", 400)
        if rfp.project_id is not None and rfp.project_id != project_id:
            raise ApiError("rfp does not belong to this project", 400)
    status = (data.get("status") or "draft").strip()
    if status not in COMMITMENT_STATUSES:
        raise ApiError("invalid status", 400)
    c = Commitment(
        project_id=project_id,
        vendor_company_id=vid,
        commitment_kind=kind,
        reference_number=(data.get("reference_number") or None) or None,
        title=str(data.get("title") or "").strip() or "Commitment",
        status=status,
        status_effective_date=_parse_date(data.get("status_effective_date")),
        approved_at=_parse_dt(data.get("approved_at")),
        workflow_rule_active=bool(data.get("workflow_rule_active")),
        retention_percentage=_dec(data.get("retention_percentage")),
        currency=str(data.get("currency") or "USD").strip()[:8] or "USD",
        total_amount=_dec(data.get("total_amount")),
        rfp_id=rfp_id,
        notes=(data.get("notes") or None) or None,
    )
    if c.status == "approved" and c.approved_at is None:
        c.approved_at = _utcnow()
    db.session.add(c)
    db.session.flush()
    db.session.commit()
    return get_commitment_detail(project_id, c.id, cu)


def patch_commitment(
    project_id: uuid.UUID, commitment_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    blocked = _commitment_blocked_for(c, cu)
    if blocked:
        turning_off = "workflow_rule_active" in data and data.get("workflow_rule_active") is False
        if turning_off:
            c.workflow_rule_active = False
            db.session.flush()
        else:
            raise ApiError("commitment is locked by an active workflow rule", 403)
    if "commitment_kind" in data or "kind" in data:
        raw = (data.get("commitment_kind") or data.get("kind") or "").strip()
        if raw and raw not in COMMITMENT_KINDS:
            raise ApiError("invalid commitment_kind", 400)
        if raw:
            c.commitment_kind = raw
    if "vendor_company_id" in data:
        vid = _parse_uuid(data.get("vendor_company_id"))
        if vid is None:
            raise ApiError("invalid vendor_company_id", 400)
        vendor = db.session.get(Company, vid)
        if vendor is None or vendor.deleted_at is not None:
            raise ApiError("vendor company not found", 400)
        if not _vendor_company_ok(vendor):
            raise ApiError("invalid vendor company type", 400)
        c.vendor_company_id = vid
    if "reference_number" in data:
        rn = data.get("reference_number")
        if rn is None or rn == "":
            c.reference_number = None
        else:
            c.reference_number = str(rn).strip() or None
    if "title" in data:
        c.title = str(data.get("title") or "").strip() or c.title
    if "status" in data:
        st = str(data.get("status") or "").strip()
        if st not in COMMITMENT_STATUSES:
            raise ApiError("invalid status", 400)
        c.status = st
        if st == "approved" and c.approved_at is None:
            c.approved_at = _utcnow()
    if "status_effective_date" in data:
        c.status_effective_date = _parse_date(data.get("status_effective_date"))
    if "approved_at" in data:
        c.approved_at = _parse_dt(data.get("approved_at"))
    if "workflow_rule_active" in data:
        c.workflow_rule_active = bool(data.get("workflow_rule_active"))
    if "retention_percentage" in data:
        c.retention_percentage = _dec(data.get("retention_percentage"))
    if "currency" in data and data.get("currency"):
        c.currency = str(data["currency"]).strip()[:8]
    if "total_amount" in data:
        c.total_amount = _dec(data.get("total_amount"))
    if "rfp_id" in data:
        rid = _parse_uuid(data.get("rfp_id"))
        if rid is not None:
            rfp = db.session.get(Rfp, rid)
            if rfp is None:
                raise ApiError("rfp not found", 400)
            if rfp.project_id is not None and rfp.project_id != project_id:
                raise ApiError("rfp does not belong to this project", 400)
        c.rfp_id = rid
    if "notes" in data:
        c.notes = (str(data["notes"]).strip() or None) if data.get("notes") is not None else None
    db.session.flush()
    db.session.commit()
    return get_commitment_detail(project_id, commitment_id, cu)


def delete_commitment(project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    if _commitment_blocked_for(c, cu):
        raise ApiError("commitment is locked by an active workflow rule", 403)
    db.session.delete(c)
    db.session.flush()
    db.session.commit()


def _ensure_cost_code_project(cost_code_id: uuid.UUID | None, project_id: uuid.UUID) -> None:
    if cost_code_id is None:
        return
    cc = db.session.get(CostCode, cost_code_id)
    if cc is None:
        raise ApiError("cost code not found", 400)
    if cc.project_id != project_id:
        raise ApiError("cost code does not belong to this project", 400)


def create_line_item(
    project_id: uuid.UUID, commitment_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    if _commitment_blocked_for(c, cu):
        raise ApiError("commitment is locked by an active workflow rule", 403)
    cc_id = _parse_uuid(data.get("cost_code_id"))
    _ensure_cost_code_project(cc_id, project_id)
    qty = _dec(data.get("quantity")) or Decimal("0")
    unit_cost = _dec(data.get("unit_cost")) or Decimal("0")
    line_total = _dec(data.get("line_total"))
    if line_total is None:
        line_total = (qty * unit_cost).quantize(Decimal("0.01"))
    li = CommitmentLineItem(
        commitment_id=commitment_id,
        cost_code_id=cc_id,
        sort_order=int(data.get("sort_order") or 0),
        description=str(data.get("description") or "").strip(),
        quantity=qty,
        unit=str(data.get("unit") or "EA").strip()[:50] or "EA",
        unit_cost=unit_cost,
        line_total=line_total,
        tax_code=(str(data["tax_code"]).strip()[:40] or None) if data.get("tax_code") else None,
        takeoff_line_item_id=_parse_uuid(data.get("takeoff_line_item_id")),
    )
    db.session.add(li)
    db.session.flush()
    db.session.commit()
    return _serialize_line(li)


def patch_line_item(
    project_id: uuid.UUID,
    commitment_id: uuid.UUID,
    line_id: uuid.UUID,
    data: Mapping[str, Any],
    cu: CurrentUser,
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    if _commitment_blocked_for(c, cu):
        raise ApiError("commitment is locked by an active workflow rule", 403)
    li = db.session.get(CommitmentLineItem, line_id)
    if li is None or li.commitment_id != commitment_id:
        raise ApiError("line item not found", 404)
    if "cost_code_id" in data:
        cc_id = _parse_uuid(data.get("cost_code_id"))
        _ensure_cost_code_project(cc_id, project_id)
        li.cost_code_id = cc_id
    if "sort_order" in data:
        li.sort_order = int(data.get("sort_order") or 0)
    if "description" in data:
        li.description = str(data.get("description") or "").strip()
    if "quantity" in data:
        li.quantity = _dec(data.get("quantity")) or Decimal("0")
    if "unit" in data:
        li.unit = str(data.get("unit") or "EA").strip()[:50] or "EA"
    if "unit_cost" in data:
        li.unit_cost = _dec(data.get("unit_cost")) or Decimal("0")
    if "line_total" in data:
        li.line_total = _dec(data.get("line_total")) or Decimal("0")
    elif "quantity" in data or "unit_cost" in data:
        li.line_total = (li.quantity * li.unit_cost).quantize(Decimal("0.01"))
    if "tax_code" in data:
        li.tax_code = (str(data["tax_code"]).strip()[:40] or None) if data.get("tax_code") else None
    if "takeoff_line_item_id" in data:
        li.takeoff_line_item_id = _parse_uuid(data.get("takeoff_line_item_id"))
    db.session.flush()
    db.session.commit()
    return _serialize_line(li)


def delete_line_item(
    project_id: uuid.UUID, commitment_id: uuid.UUID, line_id: uuid.UUID, cu: CurrentUser
) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    if _commitment_blocked_for(c, cu):
        raise ApiError("commitment is locked by an active workflow rule", 403)
    li = db.session.get(CommitmentLineItem, line_id)
    if li is None or li.commitment_id != commitment_id:
        raise ApiError("line item not found", 404)
    db.session.delete(li)
    db.session.flush()
    db.session.commit()


def list_line_items(project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    detail = get_commitment_detail(project_id, commitment_id, cu)
    return {"items": detail["line_items"], "entity": "commitment_line_items"}


def create_bill_allocation(
    project_id: uuid.UUID, commitment_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    if _commitment_blocked_for(c, cu):
        raise ApiError("commitment is locked by an active workflow rule", 403)
    ref = str(data.get("vendor_bill_ref") or "").strip()
    if not ref:
        raise ApiError("vendor_bill_ref required", 400)
    amt = _dec(data.get("allocated_amount"))
    if amt is None:
        raise ApiError("allocated_amount required", 400)
    b = CommitmentBillAllocation(
        commitment_id=commitment_id,
        vendor_bill_ref=ref[:120],
        allocated_amount=amt,
        billed_at=_parse_date(data.get("billed_at")),
        notes=(str(data["notes"]).strip() or None) if data.get("notes") else None,
    )
    db.session.add(b)
    db.session.flush()
    db.session.commit()
    return _serialize_bill(b)


def delete_bill_allocation(
    project_id: uuid.UUID, commitment_id: uuid.UUID, bill_id: uuid.UUID, cu: CurrentUser
) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_commitment(project_id, commitment_id)
    if c is None:
        raise ApiError("commitment not found", 404)
    if _commitment_blocked_for(c, cu):
        raise ApiError("commitment is locked by an active workflow rule", 403)
    b = db.session.get(CommitmentBillAllocation, bill_id)
    if b is None or b.commitment_id != commitment_id:
        raise ApiError("bill allocation not found", 404)
    db.session.delete(b)
    db.session.flush()
    db.session.commit()


def list_bill_allocations(project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    detail = get_commitment_detail(project_id, commitment_id, cu)
    return {"items": detail["bill_allocations"], "entity": "commitment_bill_allocations"}
