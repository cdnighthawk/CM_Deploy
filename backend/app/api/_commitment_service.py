"""Project-scoped commitments (PO / subcontract) API logic."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    Commitment,
    CommitmentBillAllocation,
    CommitmentLineItem,
    Company,
    Contact,
    CostCode,
    Project,
    ProjectDirectoryCompany,
    Rfp,
    User,
)
from . import _procurement_lookup_service as proc_lookup_svc
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

COMMITMENT_KINDS = frozenset({"purchase_order", "subcontract"})
COMMITMENT_STATUSES = frozenset(
    {"draft", "pending_submission", "pending", "not_approved", "approved"}
)
COMMITMENT_RESOURCES = frozenset({"material", "labor", "equipment", "subcontractor", "other"})


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


def _validate_resource(raw: Any) -> str | None:
    if raw is None or raw == "":
        return None
    val = str(raw).strip().lower()
    if val not in COMMITMENT_RESOURCES:
        raise ApiError("invalid resource", 400)
    return val


def _serialize_line(li: CommitmentLineItem) -> dict[str, Any]:
    return {
        "id": str(li.id),
        "commitment_id": str(li.commitment_id),
        "cost_code_id": str(li.cost_code_id) if li.cost_code_id else None,
        "sort_order": li.sort_order,
        "item_number": li.item_number,
        "description": li.description,
        "quantity": str(li.quantity),
        "unit": li.unit,
        "unit_cost": str(li.unit_cost),
        "line_total": str(li.line_total),
        "tax_code": li.tax_code,
        "resource": li.resource,
        "delivery_date": _iso(li.delivery_date) if li.delivery_date else None,
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


def _user_display_name(u: User | None) -> str | None:
    if u is None:
        return None
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    return name or u.email


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
        "issue_date": _iso(c.issue_date) if c.issue_date else None,
        "po_type": c.po_type,
        "reminder_date": _iso(c.reminder_date) if c.reminder_date else None,
        "vendor_contact_id": str(c.vendor_contact_id) if c.vendor_contact_id else None,
        "vendor_address_snapshot": c.vendor_address_snapshot,
        "issued_by_user_id": str(c.issued_by_user_id) if c.issued_by_user_id else None,
        "authorized_by_user_id": str(c.authorized_by_user_id) if c.authorized_by_user_id else None,
        "issued_by_address_snapshot": c.issued_by_address_snapshot,
        "ship_to_address": c.ship_to_address,
        "default_delivery_date": _iso(c.default_delivery_date) if c.default_delivery_date else None,
        "default_cost_code_id": str(c.default_cost_code_id) if c.default_cost_code_id else None,
        "default_tax_code": c.default_tax_code,
        "default_resource": c.default_resource,
        "issued_by_name": _user_display_name(db.session.get(User, c.issued_by_user_id)) if c.issued_by_user_id else None,
        "authorized_by_name": _user_display_name(db.session.get(User, c.authorized_by_user_id))
        if c.authorized_by_user_id
        else None,
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


def _ensure_cost_code_project(cost_code_id: uuid.UUID | None, project_id: uuid.UUID) -> None:
    if cost_code_id is None:
        return
    cc = db.session.get(CostCode, cost_code_id)
    if cc is None:
        raise ApiError("cost code not found", 400)
    if cc.project_id != project_id:
        raise ApiError("cost code does not belong to this project", 400)


def _apply_commitment_header_fields(
    c: Commitment, data: Mapping[str, Any], project_id: uuid.UUID, *, is_create: bool
) -> None:
    if is_create:
        kind = (data.get("commitment_kind") or data.get("kind") or "").strip()
        if kind not in COMMITMENT_KINDS:
            raise ApiError("commitment_kind must be purchase_order or subcontract", 400)
        c.commitment_kind = kind
        vid = _parse_uuid(data.get("vendor_company_id"))
        if vid is None:
            raise ApiError("vendor_company_id required", 400)
        vendor = db.session.get(Company, vid)
        if vendor is None or vendor.deleted_at is not None:
            raise ApiError("vendor company not found", 400)
        if not _vendor_company_ok(vendor):
            raise ApiError("invalid vendor company type for procurement", 400)
        c.vendor_company_id = vid
        c.project_id = project_id
    elif "vendor_company_id" in data:
        vid = _parse_uuid(data.get("vendor_company_id"))
        if vid is None:
            raise ApiError("invalid vendor_company_id", 400)
        vendor = db.session.get(Company, vid)
        if vendor is None or vendor.deleted_at is not None:
            raise ApiError("vendor company not found", 400)
        if not _vendor_company_ok(vendor):
            raise ApiError("invalid vendor company type", 400)
        c.vendor_company_id = vid

    if is_create or "commitment_kind" in data or "kind" in data:
        if not is_create:
            raw = (data.get("commitment_kind") or data.get("kind") or "").strip()
            if raw:
                if raw not in COMMITMENT_KINDS:
                    raise ApiError("invalid commitment_kind", 400)
                c.commitment_kind = raw

    if is_create or "reference_number" in data:
        if is_create or "reference_number" in data:
            rn = data.get("reference_number") if "reference_number" in data else c.reference_number
            if rn is None or rn == "":
                c.reference_number = None
            else:
                c.reference_number = str(rn).strip() or None

    if is_create or "title" in data:
        c.title = str(data.get("title") or c.title or "").strip() or "Commitment"

    if is_create or "status" in data:
        status = (data.get("status") or c.status or "draft").strip()
        if status not in COMMITMENT_STATUSES:
            raise ApiError("invalid status", 400)
        c.status = status
        if status == "approved" and c.approved_at is None:
            c.approved_at = _utcnow()

    if "status_effective_date" in data:
        c.status_effective_date = _parse_date(data.get("status_effective_date"))

    if "approved_at" in data:
            c.approved_at = _parse_dt(data.get("approved_at"))

    if is_create or "workflow_rule_active" in data:
        if "workflow_rule_active" in data or is_create:
            c.workflow_rule_active = bool(data.get("workflow_rule_active"))

    if is_create or "retention_percentage" in data:
        if "retention_percentage" in data or is_create:
            c.retention_percentage = _dec(data.get("retention_percentage"))

    if is_create or "currency" in data:
        if is_create or (data.get("currency")):
            c.currency = str(data.get("currency") or c.currency or "USD").strip()[:8] or "USD"

    if is_create or "total_amount" in data:
        if "total_amount" in data or is_create:
            c.total_amount = _dec(data.get("total_amount"))

    if is_create or "rfp_id" in data:
        if "rfp_id" in data or is_create:
            rid = _parse_uuid(data.get("rfp_id"))
            if rid is not None:
                rfp = db.session.get(Rfp, rid)
                if rfp is None:
                    raise ApiError("rfp not found", 400)
                if rfp.project_id is not None and rfp.project_id != project_id:
                    raise ApiError("rfp does not belong to this project", 400)
            c.rfp_id = rid

    if is_create or "notes" in data:
        if "notes" in data:
            c.notes = (str(data["notes"]).strip() or None) if data.get("notes") is not None else None

    if "issue_date" in data:
        c.issue_date = _parse_date(data.get("issue_date"))

    if is_create or "po_type" in data:
        pt = data.get("po_type")
        c.po_type = (str(pt).strip()[:40] or None) if pt is not None and pt != "" else None

    if is_create or "reminder_date" in data:
        c.reminder_date = _parse_date(data.get("reminder_date"))

    if is_create or "vendor_contact_id" in data:
        cid = _parse_uuid(data.get("vendor_contact_id"))
        c.vendor_contact_id = cid

    if is_create or "vendor_address_snapshot" in data:
        vas = data.get("vendor_address_snapshot")
        c.vendor_address_snapshot = (str(vas).strip() or None) if vas is not None else None

    if is_create or "issued_by_user_id" in data:
        c.issued_by_user_id = _parse_uuid(data.get("issued_by_user_id"))

    if is_create or "authorized_by_user_id" in data:
        c.authorized_by_user_id = _parse_uuid(data.get("authorized_by_user_id"))

    if is_create or "issued_by_address_snapshot" in data:
        ias = data.get("issued_by_address_snapshot")
        c.issued_by_address_snapshot = (str(ias).strip() or None) if ias is not None else None

    if is_create or "ship_to_address" in data:
        sta = data.get("ship_to_address")
        c.ship_to_address = (str(sta).strip() or None) if sta is not None else None

    if is_create or "default_delivery_date" in data:
        c.default_delivery_date = _parse_date(data.get("default_delivery_date"))

    if is_create or "default_cost_code_id" in data:
        dcc = _parse_uuid(data.get("default_cost_code_id"))
        _ensure_cost_code_project(dcc, project_id)
        c.default_cost_code_id = dcc

    if is_create or "default_tax_code" in data:
        dtc = data.get("default_tax_code")
        c.default_tax_code = (str(dtc).strip()[:40] or None) if dtc is not None and dtc != "" else None

    if is_create or "default_resource" in data:
        c.default_resource = _validate_resource(data.get("default_resource"))


def _build_line_item_from_payload(
    commitment_id: uuid.UUID,
    project_id: uuid.UUID,
    data: Mapping[str, Any],
    commitment: Commitment,
    sort_index: int,
) -> CommitmentLineItem:
    cc_id = _parse_uuid(data.get("cost_code_id"))
    if cc_id is None and commitment.default_cost_code_id:
        cc_id = commitment.default_cost_code_id
    _ensure_cost_code_project(cc_id, project_id)
    qty = _dec(data.get("quantity")) or Decimal("0")
    unit_cost = _dec(data.get("unit_cost")) or Decimal("0")
    line_total = _dec(data.get("line_total"))
    if line_total is None:
        line_total = (qty * unit_cost).quantize(Decimal("0.01"))
    tax_code = data.get("tax_code")
    if (tax_code is None or tax_code == "") and commitment.default_tax_code:
        tax_code = commitment.default_tax_code
    resource = data.get("resource")
    if (resource is None or resource == "") and commitment.default_resource:
        resource = commitment.default_resource
    delivery_date = _parse_date(data.get("delivery_date"))
    if delivery_date is None and commitment.default_delivery_date:
        delivery_date = commitment.default_delivery_date
    return CommitmentLineItem(
        commitment_id=commitment_id,
        cost_code_id=cc_id,
        sort_order=int(data.get("sort_order") if data.get("sort_order") is not None else sort_index),
        item_number=(str(data["item_number"]).strip()[:40] or None) if data.get("item_number") else None,
        description=str(data.get("description") or "").strip(),
        quantity=qty,
        unit=str(data.get("unit") or "EA").strip()[:50] or "EA",
        unit_cost=unit_cost,
        line_total=line_total,
        tax_code=(str(tax_code).strip()[:40] or None) if tax_code else None,
        resource=_validate_resource(resource),
        delivery_date=delivery_date,
        takeoff_line_item_id=_parse_uuid(data.get("takeoff_line_item_id")),
    )


def create_commitment(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    project = db.session.get(Project, project_id)
    if project is None or project.deleted_at is not None:
        raise ApiError("project not found", 404)

    ref = (data.get("reference_number") or "").strip() if data.get("reference_number") else ""
    title = str(data.get("title") or "").strip()
    kind = (data.get("commitment_kind") or data.get("kind") or "purchase_order").strip()
    if kind not in COMMITMENT_KINDS:
        raise ApiError("commitment_kind must be purchase_order or subcontract", 400)
    if kind == "purchase_order" and not ref:
        raise ApiError("reference_number (PO #) required", 400)
    if not title:
        raise ApiError("title (PO subject) required", 400)

    status = (data.get("status") or "draft").strip()
    if status != "draft" and not _parse_date(data.get("status_effective_date")):
        raise ApiError("status_effective_date required when status is not draft", 400)

    vid = _parse_uuid(data.get("vendor_company_id"))
    if vid is None:
        raise ApiError("vendor_company_id required", 400)

    c = Commitment(
        project_id=project_id,
        vendor_company_id=vid,
        commitment_kind=(data.get("commitment_kind") or data.get("kind") or "purchase_order").strip(),
        title=title,
        reference_number=ref,
        status=status,
        currency=str(data.get("currency") or "USD").strip()[:8] or "USD",
    )
    today = date.today()
    c.issue_date = _parse_date(data.get("issue_date")) or today
    if status != "draft":
        c.status_effective_date = _parse_date(data.get("status_effective_date")) or today
    else:
        c.status_effective_date = _parse_date(data.get("status_effective_date"))

    payload = dict(data)
    if not (payload.get("ship_to_address") or "").strip():
        ship = proc_lookup_svc.format_project_address(project)
        if ship:
            payload["ship_to_address"] = ship

    _apply_commitment_header_fields(c, payload, project_id, is_create=True)

    vendor = db.session.get(Company, c.vendor_company_id)
    if vendor and not (data.get("vendor_address_snapshot") or "").strip():
        c.vendor_address_snapshot = proc_lookup_svc._format_company_address(vendor)

    line_payloads = data.get("line_items")
    if line_payloads is not None and not isinstance(line_payloads, list):
        raise ApiError("line_items must be an array", 400)

    db.session.add(c)
    db.session.flush()

    line_total_sum = Decimal("0")
    if isinstance(line_payloads, list):
        for idx, lp in enumerate(line_payloads):
            if not isinstance(lp, Mapping):
                raise ApiError("each line_items entry must be an object", 400)
            desc = str(lp.get("description") or "").strip()
            if not desc and not lp.get("quantity"):
                continue
            if desc and lp.get("quantity") in (None, ""):
                raise ApiError("quantity required when line description is set", 400)
            li = _build_line_item_from_payload(c.id, project_id, lp, c, idx)
            if not li.description:
                raise ApiError("line description required", 400)
            db.session.add(li)
            line_total_sum += li.line_total
        db.session.flush()

    if c.total_amount is None and line_total_sum > 0:
        c.total_amount = line_total_sum

    if not proc_lookup_svc.is_company_in_directory(project_id, c.vendor_company_id):
        db.session.add(ProjectDirectoryCompany(project_id=project_id, company_id=c.vendor_company_id))

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
    if "status" in data:
        st = str(data.get("status") or "").strip()
        if st not in COMMITMENT_STATUSES:
            raise ApiError("invalid status", 400)
        if st != "draft" and "status_effective_date" not in data and not c.status_effective_date:
            raise ApiError("status_effective_date required when status is not draft", 400)
    _apply_commitment_header_fields(c, data, project_id, is_create=False)
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
    li = _build_line_item_from_payload(commitment_id, project_id, data, c, int(data.get("sort_order") or 0))
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
    if "item_number" in data:
        raw_in = data.get("item_number")
        li.item_number = (str(raw_in).strip()[:40] or None) if raw_in is not None and raw_in != "" else None
    if "resource" in data:
        li.resource = _validate_resource(data.get("resource"))
    if "delivery_date" in data:
        li.delivery_date = _parse_date(data.get("delivery_date"))
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
