"""Sage CM Wave 2 list/create/patch/delete plus inbox, companies, and timecards."""
from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Type

from flask import request
from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import (
    AnticipatedCost,
    AuditLog,
    Commitment,
    CommitmentLineItem,
    Company,
    CompanyInsurancePolicy,
    CompanyLicense,
    Contact,
    HrmsTimesheetEntry,
    HrmsTimesheetPeriod,
    Issue,
    IssueCompany,
    Meeting,
    Project,
    PunchlistItem,
    PurchaseOrderChangeOrder,
    QcChecklist,
    Rfi,
    SafetyIncident,
    SubInvoice,
    Submittal,
    TimeEntry,
    Transmittal,
    User,
    WorkOrder,
    WorkflowAmountRule,
    WorkflowInstance,
    WorkflowInstanceStep,
)
from ._perms import CurrentUser, is_company_readonly
from ._rfi_service import ApiError

MEETING_TYPES = frozenset({"oac", "coordination", "safety", "precon", "other"})
MEETING_STATUSES = frozenset({"scheduled", "completed", "canceled"})
POCO_STATUSES = frozenset({"draft", "issued", "approved", "void"})
SUBINV_STATUSES = frozenset({"draft", "received", "approved", "rejected", "paid"})


def _audit(
    cu: CurrentUser,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    message: str,
    changes: dict[str, Any] | None = None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=cu.id if cu else None,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            message=message,
            changes=changes,
            ip_address=(request.remote_addr or "")[:45] if request else None,
            user_agent=(request.user_agent.string or "")[:500] if request else None,
        )
    )


def _user_display_name(u: User | None) -> str | None:
    if u is None:
        return None
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    return name or u.email


def _dec(raw: Any, default: str = "0") -> Decimal:
    if raw is None or raw == "":
        return Decimal(default)
    try:
        return Decimal(str(raw).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return Decimal(default)


def _poco_amount(items: Any) -> Decimal:
    total = Decimal("0")
    if not isinstance(items, list):
        return total
    for raw in items:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("line_total") not in (None, ""):
            total += _dec(raw.get("line_total"))
            continue
        qty = _dec(raw.get("quantity"))
        price = _dec(raw.get("unit_price", raw.get("unit_cost")))
        total += (qty * price).quantize(Decimal("0.01"))
    return total.quantize(Decimal("0.01"))


def _snapshot_po_lines(comm: Commitment) -> list[dict[str, Any]]:
    out = []
    for li in list(comm.line_items or []):
        out.append(
            {
                "id": str(li.id),
                "description": li.description,
                "quantity": float(li.quantity),
                "unit": li.unit,
                "unit_cost": float(li.unit_cost),
                "line_total": float(li.line_total),
                "sort_order": li.sort_order,
                "cost_code_id": str(li.cost_code_id) if li.cost_code_id else None,
            }
        )
    return out


def _recompute_po_total(comm: Commitment) -> None:
    total = sum((li.line_total or Decimal("0")) for li in list(comm.line_items or []))
    comm.total_amount = Decimal(str(total)).quantize(Decimal("0.01"))


def _apply_poco_deltas(row: PurchaseOrderChangeOrder) -> None:
    comm = db.session.get(Commitment, row.commitment_id)
    if comm is None:
        raise ApiError("purchase order not found", 404)
    if not row.applied:
        row.line_snapshot = _snapshot_po_lines(comm)
        for raw in row.items or []:
            if not isinstance(raw, Mapping):
                continue
            action = str(raw.get("action") or "change").strip().lower()
            parent_id = _parse_uuid(raw.get("parent_po_line_id") or raw.get("commitment_line_id"))
            qty = _dec(raw.get("quantity"))
            price = _dec(raw.get("unit_price", raw.get("unit_cost")))
            desc = str(raw.get("description") or "").strip()[:500]
            unit = str(raw.get("unit") or "EA").strip()[:50] or "EA"
            if action == "add" or parent_id is None:
                li = CommitmentLineItem(
                    commitment_id=comm.id,
                    description=desc or "PO CO line",
                    quantity=qty,
                    unit=unit,
                    unit_cost=price,
                    line_total=(qty * price).quantize(Decimal("0.01")),
                    sort_order=len(list(comm.line_items or [])),
                )
                db.session.add(li)
            else:
                li = db.session.get(CommitmentLineItem, parent_id)
                if li is None or li.commitment_id != comm.id:
                    continue
                if action == "delete":
                    db.session.delete(li)
                else:
                    if desc:
                        li.description = desc
                    li.quantity = qty
                    li.unit = unit
                    li.unit_cost = price
                    li.line_total = (qty * price).quantize(Decimal("0.01"))
        db.session.flush()
        _recompute_po_total(comm)
        row.applied = True
        row.amount_applied = _poco_amount(row.items)
    # TODO(workflow_engine_cursor.md): process_key=purchase_order spend-auth if revised total crosses a band.


def _reverse_poco_deltas(row: PurchaseOrderChangeOrder) -> None:
    if not row.applied:
        return
    comm = db.session.get(Commitment, row.commitment_id)
    if comm is None:
        row.applied = False
        row.amount_applied = None
        return
    for li in list(comm.line_items or []):
        db.session.delete(li)
    db.session.flush()
    for i, raw in enumerate(row.line_snapshot or []):
        if not isinstance(raw, Mapping):
            continue
        qty = _dec(raw.get("quantity"))
        price = _dec(raw.get("unit_cost", raw.get("unit_price")))
        db.session.add(
            CommitmentLineItem(
                commitment_id=comm.id,
                description=str(raw.get("description") or "")[:500],
                quantity=qty,
                unit=str(raw.get("unit") or "EA")[:50],
                unit_cost=price,
                line_total=_dec(raw.get("line_total"), str((qty * price).quantize(Decimal("0.01")))),
                sort_order=int(raw.get("sort_order") or i),
                cost_code_id=_parse_uuid(raw.get("cost_code_id")),
            )
        )
    db.session.flush()
    _recompute_po_total(comm)
    row.applied = False
    row.amount_applied = None


def _previous_to_date(project_id: uuid.UUID, commitment_id: uuid.UUID | None, exclude_id: uuid.UUID | None) -> Decimal:
    if not commitment_id:
        return Decimal("0")
    rows = db.session.scalars(
        select(SubInvoice).where(
            SubInvoice.project_id == project_id,
            SubInvoice.commitment_id == commitment_id,
            SubInvoice.status.in_(("approved", "paid")),
        )
    ).all()
    total = Decimal("0")
    for r in rows:
        if exclude_id and r.id == exclude_id:
            continue
        total += Decimal(str(r.this_period if r.this_period is not None else r.amount or 0))
    return total.quantize(Decimal("0.01"))


def _finalize_sub_invoice(row: SubInvoice) -> None:
    lines = row.lines if isinstance(row.lines, list) else []
    this_period = Decimal("0")
    if lines:
        for raw in lines:
            if not isinstance(raw, Mapping):
                continue
            this_period += _dec(raw.get("this_period", raw.get("amount", raw.get("line_total"))))
    elif row.this_period is not None:
        this_period = Decimal(str(row.this_period))
    elif row.amount is not None:
        this_period = Decimal(str(row.amount))
    row.this_period = this_period.quantize(Decimal("0.01"))
    if row.retainage_pct is None and row.commitment_id:
        comm = db.session.get(Commitment, row.commitment_id)
        if comm is not None and comm.retention_percentage is not None:
            row.retainage_pct = Decimal(str(comm.retention_percentage))
    pct = Decimal(str(row.retainage_pct or 0))
    retainage_this = (row.this_period * pct / Decimal("100")).quantize(Decimal("0.01"))
    row.retainage = retainage_this
    row.previous_to_date = _previous_to_date(row.project_id, row.commitment_id, row.id)
    row.amount_due = (row.this_period - retainage_this).quantize(Decimal("0.01"))
    row.amount = row.this_period
    if row.status == "approved":
        row.approved = True
    elif row.status in ("rejected", "draft", "received"):
        row.approved = False


def _finalize_poco(row: PurchaseOrderChangeOrder) -> None:
    if isinstance(row.items, list):
        for raw in row.items:
            if isinstance(raw, dict) and raw.get("line_total") in (None, ""):
                qty = _dec(raw.get("quantity"))
                price = _dec(raw.get("unit_price", raw.get("unit_cost")))
                raw["line_total"] = float((qty * price).quantize(Decimal("0.01")))
    row.amount = _poco_amount(row.items)
    st = (row.status or "draft").strip()
    if st not in POCO_STATUSES:
        raise ApiError("invalid status")
    if st == "approved":
        _apply_poco_deltas(row)
    elif st == "void":
        _reverse_poco_deltas(row)


def _enrich_kind(kind: str, row, out: dict[str, Any]) -> dict[str, Any]:
    if kind == "meetings":
        fac = db.session.get(User, row.facilitator_user_id) if getattr(row, "facilitator_user_id", None) else None
        attendees = row.attendees if isinstance(row.attendees, list) else []
        out["facilitator_name"] = _user_display_name(fac)
        out["attendee_count"] = len(attendees)
        out["agenda_count"] = len(row.items) if isinstance(row.items, list) else 0
        start = row.start_time or ""
        end = row.end_time or ""
        out["time_range"] = f"{start}–{end}".strip("–") if (start or end) else ""
    elif kind == "po-change-orders":
        comm = db.session.get(Commitment, row.commitment_id) if row.commitment_id else None
        out["po_number"] = (comm.reference_number or comm.title) if comm else None
        out["po_title"] = comm.title if comm else None
        vendor = db.session.get(Company, comm.vendor_company_id) if comm else None
        out["vendor_name"] = vendor.name if vendor else None
        out["amount"] = float(row.amount) if row.amount is not None else float(_poco_amount(row.items))
        out["applied"] = bool(getattr(row, "applied", False))
    elif kind == "sub-invoices":
        comm = db.session.get(Commitment, row.commitment_id) if row.commitment_id else None
        out["subcontract_number"] = (comm.reference_number or comm.title) if comm else None
        vendor = db.session.get(Company, comm.vendor_company_id) if comm else None
        out["vendor_name"] = vendor.name if vendor else None
        out["retainage_pct"] = float(row.retainage_pct) if row.retainage_pct is not None else None
        out["this_period"] = float(row.this_period) if row.this_period is not None else None
        out["previous_to_date"] = float(row.previous_to_date) if row.previous_to_date is not None else None
        out["amount_due"] = float(row.amount_due) if row.amount_due is not None else None
        if row.period_start and row.period_end:
            out["period"] = f"{row.period_start.isoformat()} – {row.period_end.isoformat()}"
        else:
            out["period"] = None
        if comm:
            out["sov"] = [
                {
                    "id": str(li.id),
                    "description": li.description,
                    "quantity": float(li.quantity),
                    "unit": li.unit,
                    "unit_cost": float(li.unit_cost),
                    "line_total": float(li.line_total),
                }
                for li in list(comm.line_items or [])
            ]
        else:
            out["sov"] = []
    return out


def serialize_kind_row(kind: str, row) -> dict[str, Any]:
    return _enrich_kind(kind, row, serialize_row(row))


PROJECT_KINDS: dict[str, tuple[Type, str, str]] = {
    "transmittals": (Transmittal, "transmittals", "TRN"),
    "punchlist": (PunchlistItem, "punchlist_items", "PUN"),
    "work-orders": (WorkOrder, "work_orders", "WO"),
    "anticipated-costs": (AnticipatedCost, "anticipated_costs", "AC"),
    "po-change-orders": (PurchaseOrderChangeOrder, "purchase_order_change_orders", "POCO"),
    "sub-invoices": (SubInvoice, "sub_invoices", "SINV"),
    "meetings": (Meeting, "meetings", "MTG"),
    "safety-incidents": (SafetyIncident, "safety_incidents", "INC"),
    "qc-checklists": (QcChecklist, "qc_checklists", "QC"),
}


def _can_view(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard") or is_company_readonly(cu)


def _can_mutate(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser", "standard")


def _project(project_id: uuid.UUID) -> Project:
    proj = db.session.get(Project, project_id)
    if proj is None or proj.deleted_at is not None:
        raise ApiError("project not found", 404)
    return proj


def _jsonable(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return str(val)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, date):
        return val.isoformat()
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, (list, dict, bool, int, float, str)):
        return val
    return str(val)


def serialize_row(row) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for col in row.__table__.columns:
        out[col.name] = _jsonable(getattr(row, col.name))
    return out


def _next_number(model, project_id: uuid.UUID, prefix: str) -> str:
    n = db.session.scalar(select(func.count()).select_from(model).where(model.project_id == project_id)) or 0
    return f"{prefix}-{int(n) + 1:03d}"


def _next_punch_number(project_id: uuid.UUID) -> str:
    rows = db.session.scalars(select(PunchlistItem.number).where(PunchlistItem.project_id == project_id)).all()
    max_n = 0
    for num in rows:
        if not num:
            continue
        match = re.search(r"(\d+)$", str(num).strip())
        if match:
            max_n = max(max_n, int(match.group(1)))
    return str(max_n + 1)


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError as e:
        raise ApiError(f"invalid date: {raw}") from e


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError as e:
        raise ApiError("invalid id") from e


def _apply_fields(row, data: Mapping[str, Any]) -> None:
    skip = {"id", "project_id", "created_at", "updated_at"}
    for col in row.__table__.columns:
        name = col.name
        if name in skip or name not in data:
            continue
        raw = data.get(name)
        try:
            pytype = col.type.python_type
        except (NotImplementedError, AttributeError):
            pytype = type(raw) if isinstance(raw, (list, dict)) else str
        if raw is None or raw == "":
            setattr(row, name, None if col.nullable else getattr(row, name))
            continue
        if pytype is date:
            setattr(row, name, _parse_date(raw))
        elif pytype is uuid.UUID:
            setattr(row, name, _parse_uuid(raw))
        elif pytype is Decimal:
            try:
                setattr(row, name, Decimal(str(raw).replace(",", "")))
            except (InvalidOperation, ValueError) as e:
                raise ApiError(f"invalid {name}") from e
        elif pytype is bool:
            setattr(row, name, bool(raw) if not isinstance(raw, str) else raw.strip().lower() in ("1", "true", "yes"))
        elif pytype is int:
            setattr(row, name, int(raw))
        elif pytype in (list, dict):
            setattr(row, name, raw if isinstance(raw, (list, dict)) else [])
        else:
            setattr(row, name, str(raw)[:500] if name in ("subject", "title") else (str(raw) if raw is not None else None))


def list_project_kind(project_id: uuid.UUID, kind: str, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, _prefix = spec
    rows = db.session.scalars(select(model).where(model.project_id == project_id).order_by(model.created_at.desc())).all()
    out: dict[str, Any] = {"entity": entity, "items": [serialize_kind_row(kind, r) for r in rows]}
    if kind == "punchlist":
        out["next_number"] = _next_punch_number(project_id)
    return out


def get_project_kind(project_id: uuid.UUID, kind: str, row_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, _prefix = spec
    row = db.session.get(model, row_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)
    return {"item": serialize_kind_row(kind, row), "entity": entity}


def create_project_kind(project_id: uuid.UUID, kind: str, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, prefix = spec
    row = model(project_id=project_id)
    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()
    _apply_fields(row, data)
    title = getattr(row, "subject", None) or getattr(row, "title", None)
    if not title:
        raise ApiError("subject or title is required")
    if kind == "po-change-orders" and not getattr(row, "commitment_id", None):
        raise ApiError("commitment_id is required")
    if kind == "sub-invoices" and not getattr(row, "commitment_id", None):
        raise ApiError("commitment_id is required")
    if kind == "meetings":
        mt = (row.meeting_type or "other").strip() or "other"
        if mt not in MEETING_TYPES:
            raise ApiError("invalid meeting type")
        row.meeting_type = mt
        st = (row.status or "scheduled").strip() or "scheduled"
        if st not in MEETING_STATUSES:
            raise ApiError("invalid status")
        row.status = st
        if not isinstance(row.attendees, list):
            row.attendees = []
        if not isinstance(row.items, list):
            row.items = []
    if kind == "po-change-orders":
        if not isinstance(row.items, list) or not row.items:
            raise ApiError("at least one line item is required")
        _finalize_poco(row)
    if kind == "sub-invoices":
        st = (row.status or "draft").strip()
        if st not in SUBINV_STATUSES:
            raise ApiError("invalid status")
        row.status = st
        if not isinstance(row.lines, list):
            row.lines = []
        _finalize_sub_invoice(row)
    if kind == "punchlist":
        if getattr(row, "distribution_user_ids", None) is None:
            row.distribution_user_ids = []
        if getattr(row, "attachments", None) is None:
            row.attachments = []
        ids = []
        for raw in row.distribution_user_ids or []:
            uid = _parse_uuid(raw.get("id") if isinstance(raw, Mapping) else raw)
            if uid:
                ids.append(str(uid))
        row.distribution_user_ids = ids
    if hasattr(row, "number") and not getattr(row, "number", None):
        row.number = _next_punch_number(project_id) if kind == "punchlist" else _next_number(model, project_id, prefix)
    db.session.add(row)
    _audit(cu, entity, row.id, "create", f"Created {kind} {getattr(row, 'number', '') or row.id}")
    db.session.commit()
    return {"item": serialize_kind_row(kind, row), "entity": entity}


def patch_project_kind(
    project_id: uuid.UUID, kind: str, row_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, entity, _prefix = spec
    row = db.session.get(model, row_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)
    before_status = getattr(row, "status", None)
    _apply_fields(row, data)
    if kind == "po-change-orders":
        _finalize_poco(row)
    if kind == "sub-invoices":
        _finalize_sub_invoice(row)
    if kind == "meetings" and row.meeting_type and row.meeting_type not in MEETING_TYPES:
        raise ApiError("invalid meeting type")
    after_status = getattr(row, "status", None)
    if before_status != after_status:
        _audit(cu, entity, row.id, "status", f"{kind} {getattr(row, 'number', '')} {before_status} → {after_status}")
    db.session.commit()
    return {"item": serialize_kind_row(kind, row), "entity": entity}


def delete_project_kind(project_id: uuid.UUID, kind: str, row_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    spec = PROJECT_KINDS.get(kind)
    if spec is None:
        raise ApiError("unknown kind", 400)
    model, _entity, _prefix = spec
    row = db.session.get(model, row_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()


def list_companies(cu: CurrentUser, q: str = "", limit: int = 50) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    stmt = select(Company).where(Company.deleted_at.is_(None)).order_by(Company.name.asc())
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Company.name.ilike(like), Company.email.ilike(like)))
    rows = db.session.scalars(stmt.limit(max(1, min(limit, 200)))).all()
    return {"entity": "companies", "items": [_company_public(c) for c in rows]}


def _company_public(c: Company) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "name": c.name,
        "company_type": c.company_type,
        "phone": c.phone,
        "email": c.email,
        "city": c.city,
        "state": c.state,
        "website": c.website,
        "notes": c.notes,
    }


def create_company(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    name = str(data.get("name") or "").strip()
    if not name:
        raise ApiError("name is required")
    ctype = str(data.get("company_type") or "other").strip() or "other"
    row = Company(name=name[:255], company_type=ctype)
    for key in ("phone", "email", "website", "city", "state", "postal_code", "address_line1", "address_line2", "tax_id", "notes"):
        if key in data:
            setattr(row, key, (str(data.get(key) or "").strip() or None))
    db.session.add(row)
    db.session.commit()
    return {"item": _company_public(row), "entity": "company"}


def patch_company(company_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(Company, company_id)
    if row is None or row.deleted_at is not None:
        raise ApiError("company not found", 404)
    for key in ("name", "company_type", "phone", "email", "website", "city", "state", "postal_code", "address_line1", "address_line2", "tax_id", "notes"):
        if key in data:
            val = str(data.get(key) or "").strip() or None
            if key == "name" and not val:
                raise ApiError("name is required")
            setattr(row, key, val)
    db.session.commit()
    return {"item": _company_public(row), "entity": "company"}


def list_contacts(company_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    rows = db.session.scalars(
        select(Contact).where(Contact.company_id == company_id).order_by(Contact.last_name, Contact.first_name)
    ).all()
    return {
        "entity": "contacts",
        "items": [
            {
                "id": str(c.id),
                "company_id": str(c.company_id) if c.company_id else None,
                "first_name": c.first_name,
                "last_name": c.last_name,
                "title": c.title,
                "email": c.email,
                "phone": c.phone,
                "is_primary": c.is_primary,
            }
            for c in rows
        ],
    }


def create_contact(company_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    row = Contact(company_id=company_id)
    for key in ("first_name", "last_name", "title", "email", "phone", "mobile", "notes"):
        if key in data:
            setattr(row, key, (str(data.get(key) or "").strip() or None))
    if "is_primary" in data:
        row.is_primary = bool(data.get("is_primary"))
    db.session.add(row)
    db.session.commit()
    return list_contacts(company_id, cu)


def list_company_docs(company_id: uuid.UUID, kind: str, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    model = CompanyInsurancePolicy if kind == "insurance" else CompanyLicense
    rows = db.session.scalars(select(model).where(model.company_id == company_id).order_by(model.created_at.desc())).all()
    return {"entity": kind, "items": [serialize_row(r) for r in rows]}


def create_company_doc(company_id: uuid.UUID, kind: str, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Company, company_id) is None:
        raise ApiError("company not found", 404)
    model = CompanyInsurancePolicy if kind == "insurance" else CompanyLicense
    row = model(company_id=company_id)
    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()
    _apply_fields(row, data)
    db.session.add(row)
    db.session.commit()
    return {"item": serialize_row(row), "entity": kind}


def delete_company_doc(company_id: uuid.UUID, kind: str, row_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    model = CompanyInsurancePolicy if kind == "insurance" else CompanyLicense
    row = db.session.get(model, row_id)
    if row is None or row.company_id != company_id:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()


def list_amount_rules(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(select(WorkflowAmountRule).order_by(WorkflowAmountRule.min_amount.asc())).all()
    return {"entity": "workflow_amount_rules", "items": [serialize_row(r) for r in rows]}


def create_amount_rule(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    ttype = str(data.get("transaction_type") or "").strip()
    if not ttype:
        raise ApiError("transaction_type is required")
    row = WorkflowAmountRule(transaction_type=ttype)
    if getattr(row, "id", None) is None:
        row.id = uuid.uuid4()
    _apply_fields(row, data)
    db.session.add(row)
    db.session.commit()
    return {"item": serialize_row(row), "entity": "workflow_amount_rule"}


def matching_amount_rules(transaction_type: str, amount: Decimal) -> list[WorkflowAmountRule]:
    rows = db.session.scalars(
        select(WorkflowAmountRule).where(
            WorkflowAmountRule.transaction_type == transaction_type,
            WorkflowAmountRule.is_active.is_(True),
            WorkflowAmountRule.min_amount <= amount,
        )
    ).all()
    return list(rows)


def set_issue_companies(issue_id: uuid.UUID, company_ids: list[Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    issue = db.session.get(Issue, issue_id)
    if issue is None:
        raise ApiError("issue not found", 404)
    existing = db.session.scalars(select(IssueCompany).where(IssueCompany.issue_id == issue_id)).all()
    for row in existing:
        db.session.delete(row)
    for raw in company_ids:
        cid = _parse_uuid(raw.get("company_id") if isinstance(raw, Mapping) else raw)
        if not cid:
            continue
        if db.session.get(Company, cid) is None:
            continue
        role = raw.get("role") if isinstance(raw, Mapping) else None
        db.session.add(IssueCompany(issue_id=issue_id, company_id=cid, role=(str(role).strip()[:80] if role else None)))
    db.session.commit()
    return list_issue_companies(issue_id, cu)


def list_issue_companies(issue_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(select(IssueCompany).where(IssueCompany.issue_id == issue_id)).all()
    items = []
    for row in rows:
        company = db.session.get(Company, row.company_id)
        items.append(
            {
                "id": str(row.id),
                "company_id": str(row.company_id),
                "name": company.name if company else None,
                "role": row.role,
            }
        )
    return {"entity": "issue_companies", "items": items}


def workflow_inbox(cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    if not cu.id:
        return {"entity": "workflow_inbox", "items": []}
    rows = db.session.scalars(
        select(WorkflowInstanceStep)
        .where(
            WorkflowInstanceStep.assignee_user_id == cu.id,
            WorkflowInstanceStep.status.in_(("pending", "open")),
        )
        .order_by(WorkflowInstanceStep.created_at.desc())
        .limit(100)
    ).all()
    items = []
    for step in rows:
        inst = db.session.get(WorkflowInstance, step.instance_id) if getattr(step, "instance_id", None) else None
        items.append(
            {
                "id": str(step.id),
                "status": step.status,
                "subject_type": getattr(inst, "subject_type", None) if inst else None,
                "subject_id": str(inst.subject_id) if inst and inst.subject_id else None,
                "created_at": step.created_at.isoformat() if step.created_at else None,
            }
        )
    return {"entity": "workflow_inbox", "items": items}


def team_open_items(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    _project(project_id)
    items: list[dict[str, Any]] = []
    for rfi in db.session.scalars(
        select(Rfi).where(Rfi.project_id == project_id, Rfi.status.notin_(("closed", "closed_draft"))).limit(50)
    ).all():
        items.append({"kind": "rfi", "id": str(rfi.id), "title": rfi.subject or str(rfi.number), "status": rfi.status})
    for sub in db.session.scalars(
        select(Submittal).where(Submittal.project_id == project_id).limit(50)
    ).all():
        st = getattr(sub, "status", None) or ""
        if str(st).lower() in ("closed", "approved", "void"):
            continue
        items.append({"kind": "submittal", "id": str(sub.id), "title": getattr(sub, "title", None) or getattr(sub, "number", None), "status": st})
    for punch in db.session.scalars(
        select(PunchlistItem).where(PunchlistItem.project_id == project_id, PunchlistItem.status != "closed").limit(50)
    ).all():
        items.append({"kind": "punch", "id": str(punch.id), "title": punch.title, "status": punch.status})
    for iss in db.session.scalars(
        select(Issue).where(Issue.project_id == project_id, Issue.status.notin_(("Closed", "Resolved", "Done"))).limit(50)
    ).all():
        items.append({"kind": "issue", "id": str(iss.id), "title": iss.title, "status": iss.status})
    soon = date.today() + timedelta(days=30)
    for pol in db.session.scalars(select(CompanyInsurancePolicy).where(CompanyInsurancePolicy.expires_on.is_not(None)).limit(100)).all():
        if pol.expires_on and pol.expires_on <= soon:
            items.append(
                {
                    "kind": "insurance",
                    "id": str(pol.id),
                    "title": f"{pol.policy_type or 'Policy'} expires {pol.expires_on.isoformat()}",
                    "status": "expiring",
                }
            )
    return {"entity": "open_items", "items": items}


def convert_clock_to_timecard(cu: CurrentUser, data: Mapping[str, Any]) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if not cu.id:
        raise ApiError("sign in required", 401)
    start = _parse_date(data.get("period_start")) or date.today() - timedelta(days=date.today().weekday())
    end = _parse_date(data.get("period_end")) or start + timedelta(days=6)
    period = db.session.scalar(
        select(HrmsTimesheetPeriod).where(
            HrmsTimesheetPeriod.user_id == cu.id,
            HrmsTimesheetPeriod.period_start == start,
        )
    )
    if period is None:
        period = HrmsTimesheetPeriod(user_id=cu.id, period_start=start, period_end=end, status="draft")
        db.session.add(period)
        db.session.flush()
    entries = db.session.scalars(
        select(TimeEntry).where(
            TimeEntry.user_id == cu.id,
            TimeEntry.status == "closed",
            TimeEntry.started_at >= datetime.combine(start, datetime.min.time()).replace(tzinfo=timezone.utc),
            TimeEntry.started_at < datetime.combine(end + timedelta(days=1), datetime.min.time()).replace(tzinfo=timezone.utc),
        )
    ).all()
    created = 0
    for ent in entries:
        already = db.session.scalar(select(HrmsTimesheetEntry).where(HrmsTimesheetEntry.time_entry_id == ent.id))
        if already:
            continue
        hours = Decimal("0")
        if ent.ended_at and ent.started_at:
            hours = Decimal(str(round((ent.ended_at - ent.started_at).total_seconds() / 3600, 2)))
        row = HrmsTimesheetEntry(
            period_id=period.id,
            work_date=ent.started_at.date(),
            hours_worked=hours,
            notes=ent.note,
            project_id=ent.project_id,
            cost_code_id=ent.cost_code_id,
            time_entry_id=ent.id,
        )
        db.session.add(row)
        created += 1
    db.session.commit()
    rows = db.session.scalars(select(HrmsTimesheetEntry).where(HrmsTimesheetEntry.period_id == period.id)).all()
    return {
        "entity": "timesheet_period",
        "item": {
            "id": str(period.id),
            "period_start": period.period_start.isoformat(),
            "period_end": period.period_end.isoformat(),
            "status": period.status,
            "converted": created,
            "entries": [
                {
                    "id": str(e.id),
                    "work_date": e.work_date.isoformat(),
                    "hours_worked": float(e.hours_worked),
                    "project_id": str(e.project_id) if e.project_id else None,
                    "cost_code_id": str(e.cost_code_id) if e.cost_code_id else None,
                    "notes": e.notes,
                }
                for e in rows
            ],
        },
    }
