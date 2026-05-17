"""Project material order tracking (vendor-grouped, PO-linked)."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any, Mapping, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Commitment, Company, Project, ProjectMaterialOrder
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

MATERIAL_ORDER_STATUSES = frozenset({"draft", "ordered", "shipped", "delivered", "cancelled"})


def _iso(d: date | None) -> str | None:
    if d is None:
        return None
    return d.isoformat()


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


def _compute_order_date(anchor: date | None, lead_days: int | None, explicit: date | None) -> date | None:
    if explicit:
        return explicit
    if anchor and lead_days is not None and lead_days >= 0:
        return anchor - timedelta(days=lead_days)
    return None


def _compute_expected_delivery(
    order_date: date | None, lead_days: int | None, explicit: date | None
) -> date | None:
    if explicit:
        return explicit
    if order_date and lead_days is not None and lead_days >= 0:
        return order_date + timedelta(days=lead_days)
    return None


def _order_public(row: ProjectMaterialOrder) -> dict[str, Any]:
    c = row.commitment
    return {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "commitment_id": str(row.commitment_id),
        "commitment_ref": c.reference_number if c else None,
        "commitment_title": c.title if c else None,
        "vendor_company_id": str(row.vendor_company_id) if row.vendor_company_id else None,
        "vendor_name": row.vendor_name,
        "description": row.description,
        "order_date": _iso(row.order_date),
        "lead_time_days": row.lead_time_days,
        "schedule_anchor_date": _iso(row.schedule_anchor_date),
        "expected_delivery_date": _iso(row.expected_delivery_date),
        "shipping_company": row.shipping_company,
        "tracking_number": row.tracking_number,
        "status": row.status,
        "sort_order": row.sort_order,
        "notes": row.notes,
    }


def _load_commitment(pid: uuid.UUID, cid: uuid.UUID) -> Commitment:
    c = db.session.scalar(
        select(Commitment)
        .where(Commitment.id == cid, Commitment.project_id == pid)
        .options(selectinload(Commitment.vendor))
    )
    if c is None:
        raise ApiError("commitment not found for this project", 404)
    if c.commitment_kind != "purchase_order":
        raise ApiError("material orders must link to a purchase order commitment", 400)
    return c


def list_material_orders(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    rows = db.session.scalars(
        select(ProjectMaterialOrder)
        .where(ProjectMaterialOrder.project_id == project_id)
        .options(selectinload(ProjectMaterialOrder.commitment).selectinload(Commitment.vendor))
        .order_by(
            ProjectMaterialOrder.vendor_name.asc(),
            ProjectMaterialOrder.sort_order.asc(),
            ProjectMaterialOrder.created_at.asc(),
        )
    ).all()
    return {"entity": "project_material_orders", "items": [_order_public(r) for r in rows]}


def create_material_order(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    if db.session.get(Project, project_id) is None:
        raise ApiError("project not found", 404)
    cid = _parse_uuid(data.get("commitment_id"))
    if not cid:
        raise ApiError("commitment_id is required (PO)", 400)
    commitment = _load_commitment(project_id, cid)

    vendor_name = str(data.get("vendor_name") or "").strip()
    if not vendor_name and commitment.vendor:
        vendor_name = commitment.vendor.name or ""
    if not vendor_name:
        raise ApiError("vendor_name is required", 400)

    lead = data.get("lead_time_days")
    try:
        lead_days = int(lead) if lead is not None and str(lead).strip() != "" else None
    except (TypeError, ValueError):
        lead_days = None

    anchor = _parse_date(data.get("schedule_anchor_date"))
    explicit_order = _parse_date(data.get("order_date"))
    order_date = _compute_order_date(anchor, lead_days, explicit_order)
    explicit_delivery = _parse_date(data.get("expected_delivery_date"))
    expected = _compute_expected_delivery(order_date, lead_days, explicit_delivery)

    status = str(data.get("status") or "draft").strip()[:40]
    if status not in MATERIAL_ORDER_STATUSES:
        status = "draft"

    try:
        sort_order = int(data.get("sort_order") or 0)
    except (TypeError, ValueError):
        sort_order = 0

    row = ProjectMaterialOrder(
        project_id=project_id,
        commitment_id=cid,
        vendor_company_id=commitment.vendor_company_id,
        vendor_name=vendor_name[:300],
        description=(str(data.get("description")).strip() or None) if data.get("description") else None,
        order_date=order_date,
        lead_time_days=lead_days,
        schedule_anchor_date=anchor,
        expected_delivery_date=expected,
        shipping_company=(str(data.get("shipping_company")).strip()[:200] or None)
        if data.get("shipping_company")
        else None,
        tracking_number=(str(data.get("tracking_number")).strip()[:120] or None)
        if data.get("tracking_number")
        else None,
        status=status,
        sort_order=sort_order,
        notes=(str(data.get("notes")).strip() or None) if data.get("notes") else None,
    )
    db.session.add(row)
    db.session.commit()
    db.session.refresh(row, attribute_names=["commitment"])
    return {"entity": "project_material_order", "item": _order_public(row)}


def patch_material_order(
    project_id: uuid.UUID, order_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(ProjectMaterialOrder, order_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)

    if "commitment_id" in data:
        cid = _parse_uuid(data.get("commitment_id"))
        if not cid:
            raise ApiError("commitment_id cannot be empty", 400)
        commitment = _load_commitment(project_id, cid)
        row.commitment_id = cid
        row.vendor_company_id = commitment.vendor_company_id

    if "vendor_name" in data:
        vn = str(data.get("vendor_name") or "").strip()
        if vn:
            row.vendor_name = vn[:300]
    if "description" in data:
        v = data.get("description")
        row.description = (str(v).strip() or None) if v not in (None, "") else None
    if "lead_time_days" in data:
        lead = data.get("lead_time_days")
        try:
            row.lead_time_days = int(lead) if lead is not None and str(lead).strip() != "" else None
        except (TypeError, ValueError):
            raise ApiError("invalid lead_time_days", 400)
    if "schedule_anchor_date" in data:
        row.schedule_anchor_date = _parse_date(data.get("schedule_anchor_date"))
    if "order_date" in data:
        row.order_date = _parse_date(data.get("order_date"))
    elif "schedule_anchor_date" in data or "lead_time_days" in data:
        row.order_date = _compute_order_date(row.schedule_anchor_date, row.lead_time_days, row.order_date)
    if "expected_delivery_date" in data:
        row.expected_delivery_date = _parse_date(data.get("expected_delivery_date"))
    elif "order_date" in data or "lead_time_days" in data:
        row.expected_delivery_date = _compute_expected_delivery(
            row.order_date, row.lead_time_days, row.expected_delivery_date
        )
    if "shipping_company" in data:
        v = data.get("shipping_company")
        row.shipping_company = (str(v).strip()[:200] or None) if v not in (None, "") else None
    if "tracking_number" in data:
        v = data.get("tracking_number")
        row.tracking_number = (str(v).strip()[:120] or None) if v not in (None, "") else None
    if "status" in data and data.get("status"):
        st = str(data.get("status")).strip()[:40]
        if st in MATERIAL_ORDER_STATUSES:
            row.status = st
    if "notes" in data:
        v = data.get("notes")
        row.notes = (str(v).strip() or None) if v not in (None, "") else None

    db.session.commit()
    db.session.refresh(row, attribute_names=["commitment"])
    return {"entity": "project_material_order", "item": _order_public(row)}


def delete_material_order(project_id: uuid.UUID, order_id: uuid.UUID, cu: CurrentUser) -> None:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    row = db.session.get(ProjectMaterialOrder, order_id)
    if row is None or row.project_id != project_id:
        raise ApiError("not found", 404)
    db.session.delete(row)
    db.session.commit()
