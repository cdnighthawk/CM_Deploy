"""First-class Estimate CRUD, lock/approve, and takeoff copy helpers."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Company, DrawingSet, Estimate, LeadEstimate, TakeoffLineItem, User
from ._serializers import iso, lead_estimate_public, num_or_none

ESTIMATE_STATUSES = ("draft", "submitted", "awarded", "superseded", "archived")
_LINE_COPY_SKIP = frozenset({"id", "created_at", "updated_at", "estimate_id"})


class EstimateError(Exception):
    def __init__(self, message: str, status: int = 400, error_code: str | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.error_code = error_code


def estimate_locked_payload() -> dict[str, str]:
    return {
        "error": "estimate is locked (approved or manually locked); admin unlock required to edit takeoff",
        "error_code": "ESTIMATE_LOCKED",
    }


def normalize_status(raw: Any, *, default: str = "draft") -> str:
    s = str(raw or "").strip().lower()
    if s in ESTIMATE_STATUSES:
        return s
    if not s:
        return default
    return s[:40] or default


def estimate_is_locked(row: Estimate | None) -> bool:
    return row is not None and row.estimate_locked_at is not None


def current_estimate_for_lead(lead: LeadEstimate | None) -> Estimate | None:
    if lead is None or getattr(lead, "id", None) is None:
        return None
    if lead.primary_estimate_id:
        est = db.session.get(Estimate, lead.primary_estimate_id)
        if est is not None and est.lead_estimate_id == lead.id:
            return est
    return db.session.scalar(
        select(Estimate)
        .where(Estimate.lead_estimate_id == lead.id, Estimate.is_current.is_(True))
        .order_by(Estimate.created_at.asc())
    ) or db.session.scalar(
        select(Estimate)
        .where(Estimate.lead_estimate_id == lead.id)
        .order_by(Estimate.created_at.asc(), Estimate.id.asc())
    )


def mark_current(est: Estimate) -> None:
    if est.lead_estimate_id is None:
        est.is_current = True
        return
    others = db.session.scalars(
        select(Estimate).where(
            Estimate.lead_estimate_id == est.lead_estimate_id,
            Estimate.id != est.id,
            Estimate.is_current.is_(True),
        )
    ).all()
    for other in others:
        other.is_current = False
    if others:
        db.session.flush()
    est.is_current = True
    lead = db.session.get(LeadEstimate, est.lead_estimate_id)
    if lead is not None:
        lead.primary_estimate_id = est.id


def ensure_current_estimate(lead: LeadEstimate, *, user_id: uuid.UUID | None = None) -> Estimate:
    existing = current_estimate_for_lead(lead)
    if existing is not None:
        return existing
    awarded = (lead.crm_stage or "").strip().lower() == "awarded"
    est = Estimate(
        lead_estimate_id=lead.id,
        project_id=lead.project_id,
        name="Original Estimate",
        title="Original Estimate",
        status="awarded" if awarded else "draft",
        version=1,
        fee_percentage=lead.fee_percentage if lead.fee_percentage is not None else Decimal("0"),
        profit_margin=lead.profit_margin,
        rom=lead.rom,
        estimate_locked_at=lead.estimate_locked_at,
        approved_at=lead.estimate_approved_at,
        due_at=lead.due_at,
        created_by_id=user_id,
    )
    db.session.add(est)
    db.session.flush()
    mark_current(est)
    return est


def _decimal_or_none(val: Any) -> Decimal | None:
    if val is None or val == "":
        return None
    if isinstance(val, bool):
        raise EstimateError("invalid number")
    if isinstance(val, Decimal):
        return val
    if isinstance(val, int | float):
        return Decimal(str(val))
    s = str(val).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except Exception as exc:
        raise EstimateError("invalid number") from exc


def _decimal_or_zero(val: Any) -> Decimal:
    parsed = _decimal_or_none(val)
    return parsed if parsed is not None else Decimal("0")


def drawing_set_public(row: DrawingSet) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "lead_estimate_id": str(row.lead_estimate_id),
        "name": row.name,
        "issued_date": row.issued_date.isoformat() if row.issued_date else None,
        "notes": row.notes,
        "created_at": iso(row.created_at),
        "updated_at": iso(row.updated_at),
    }


def estimate_summary_public(est: Estimate) -> dict[str, Any]:
    total = est.total
    if total is None:
        total = db.session.scalar(
            select(func.coalesce(func.sum(TakeoffLineItem.extended_total), 0)).where(
                TakeoffLineItem.estimate_id == est.id
            )
        )
    ds = est.drawing_set
    return {
        "id": str(est.id),
        "lead_estimate_id": str(est.lead_estimate_id) if est.lead_estimate_id else None,
        "project_id": str(est.project_id) if est.project_id else None,
        "name": est.name,
        "title": est.title or est.name,
        "version": est.version,
        "version_label": est.version_label,
        "status": normalize_status(est.status),
        "gc_company_id": str(est.gc_company_id) if est.gc_company_id else None,
        "gc_name": est.gc_name or (est.gc_company.name if est.gc_company is not None else None),
        "drawing_set_id": str(est.drawing_set_id) if est.drawing_set_id else None,
        "drawing_set": drawing_set_public(ds) if ds is not None else None,
        "fee_percentage": num_or_none(est.fee_percentage),
        "profit_margin": num_or_none(est.profit_margin),
        "rom": num_or_none(est.rom),
        "is_current": bool(est.is_current),
        "estimate_locked_at": iso(est.estimate_locked_at),
        "approved_at": iso(est.approved_at),
        "created_from_id": str(est.created_from_id) if est.created_from_id else None,
        "created_by_id": str(est.created_by_id) if est.created_by_id else None,
        "due_at": iso(est.due_at),
        "notes": est.notes,
        "total": float(total) if total is not None else None,
        "created_at": iso(est.created_at),
        "updated_at": iso(est.updated_at),
    }


def overlay_estimate_on_lead_detail(out: dict[str, Any], est: Estimate) -> dict[str, Any]:
    out["current_estimate_id"] = str(est.id)
    out["fee_percentage"] = num_or_none(est.fee_percentage)
    out["profit_margin"] = num_or_none(est.profit_margin)
    out["rom"] = num_or_none(est.rom)
    out["estimate_locked_at"] = iso(est.estimate_locked_at) or out.get("estimate_locked_at")
    out["estimate_approved_at"] = iso(est.approved_at) or out.get("estimate_approved_at")
    return out


def takeoff_lines_for_estimate(estimate_id: uuid.UUID) -> list[TakeoffLineItem]:
    return list(
        db.session.scalars(
            select(TakeoffLineItem)
            .where(TakeoffLineItem.estimate_id == estimate_id)
            .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
            .options(joinedload(TakeoffLineItem.material_price))
        ).all()
    )


def takeoff_lines_for_lead_compat(lead: LeadEstimate) -> list[TakeoffLineItem]:
    est = current_estimate_for_lead(lead)
    if est is not None:
        return takeoff_lines_for_estimate(est.id)
    return list(
        db.session.scalars(
            select(TakeoffLineItem)
            .where(TakeoffLineItem.lead_estimate_id == lead.id)
            .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
            .options(joinedload(TakeoffLineItem.material_price))
        ).all()
    )


def next_sort_order(*, estimate_id: uuid.UUID | None = None, lead_estimate_id: uuid.UUID | None = None) -> int:
    q = select(func.coalesce(func.max(TakeoffLineItem.sort_order), -1))
    if estimate_id:
        q = q.where(TakeoffLineItem.estimate_id == estimate_id)
    elif lead_estimate_id:
        q = q.where(TakeoffLineItem.lead_estimate_id == lead_estimate_id)
    else:
        return 0
    m = db.session.scalar(q)
    return int(m if m is not None else -1) + 1


def _copy_takeoff_line(src: TakeoffLineItem, *, estimate_id: uuid.UUID, lead_estimate_id: uuid.UUID | None) -> TakeoffLineItem:
    dest = TakeoffLineItem()
    for col in TakeoffLineItem.__table__.columns:
        if col.name in _LINE_COPY_SKIP:
            continue
        setattr(dest, col.name, getattr(src, col.name))
    dest.estimate_id = estimate_id
    dest.lead_estimate_id = lead_estimate_id
    return dest


def _resolve_gc_company(raw_id: Any) -> uuid.UUID | None:
    if raw_id is None or raw_id == "":
        return None
    try:
        cid = uuid.UUID(str(raw_id).strip())
    except ValueError as exc:
        raise EstimateError("invalid gc_company_id") from exc
    if db.session.get(Company, cid) is None:
        raise EstimateError("gc company not found", status=404)
    return cid


def _resolve_drawing_set(raw_id: Any, lead_id: uuid.UUID | None) -> uuid.UUID | None:
    if raw_id is None or raw_id == "":
        return None
    try:
        did = uuid.UUID(str(raw_id).strip())
    except ValueError as exc:
        raise EstimateError("invalid drawing_set_id") from exc
    ds = db.session.get(DrawingSet, did)
    if ds is None:
        raise EstimateError("drawing set not found", status=404)
    if lead_id is not None and ds.lead_estimate_id != lead_id:
        raise EstimateError("drawing set does not belong to this lead")
    return did


def _apply_create_fields(est: Estimate, data: Mapping[str, Any], lead: LeadEstimate | None) -> None:
    name = str(data.get("name") or data.get("title") or "").strip()[:255]
    if name:
        est.name = name
        est.title = name
    if "version_label" in data:
        vl = data.get("version_label")
        est.version_label = str(vl).strip()[:64] or None if vl is not None else None
    if "gc_name" in data:
        gn = data.get("gc_name")
        est.gc_name = str(gn).strip()[:255] or None if gn is not None else None
    if "gc_company_id" in data:
        est.gc_company_id = _resolve_gc_company(data.get("gc_company_id"))
        if est.gc_company_id and not est.gc_name:
            company = db.session.get(Company, est.gc_company_id)
            if company is not None:
                est.gc_name = company.name
    if "drawing_set_id" in data:
        est.drawing_set_id = _resolve_drawing_set(data.get("drawing_set_id"), est.lead_estimate_id)
    if "fee_percentage" in data:
        est.fee_percentage = _decimal_or_zero(data.get("fee_percentage"))
    elif lead is not None and est.fee_percentage is None:
        est.fee_percentage = lead.fee_percentage if lead.fee_percentage is not None else Decimal("0")
    if "profit_margin" in data:
        est.profit_margin = _decimal_or_none(data.get("profit_margin"))
    if "rom" in data:
        est.rom = _decimal_or_none(data.get("rom"))
    if "notes" in data:
        n = data.get("notes")
        est.notes = str(n) if n is not None else None
    if "status" in data and data["status"] is not None:
        est.status = normalize_status(data.get("status"))


def create_estimate(
    lead: LeadEstimate,
    data: Mapping[str, Any],
    *,
    user_id: uuid.UUID | None = None,
    make_current: bool = False,
) -> Estimate:
    copy_raw = data.get("copy_from_estimate_id")
    source: Estimate | None = None
    if copy_raw:
        try:
            sid = uuid.UUID(str(copy_raw).strip())
        except ValueError as exc:
            raise EstimateError("invalid copy_from_estimate_id") from exc
        source = db.session.get(Estimate, sid)
        if source is None:
            raise EstimateError("copy source estimate not found", status=404)
        if source.lead_estimate_id != lead.id:
            raise EstimateError("copy source estimate must belong to the same lead")

    name = str(data.get("name") or data.get("title") or "").strip()[:255]
    if not name:
        name = "New Estimate" if source is None else f"{source.name} copy"

    est = Estimate(
        lead_estimate_id=lead.id,
        project_id=lead.project_id or (source.project_id if source else None),
        name=name,
        title=name,
        status="draft",
        version=1,
        created_by_id=user_id,
        created_from_id=source.id if source else None,
        fee_percentage=source.fee_percentage if source is not None else (lead.fee_percentage or Decimal("0")),
        profit_margin=source.profit_margin if source is not None else lead.profit_margin,
        rom=source.rom if source is not None else lead.rom,
        gc_company_id=source.gc_company_id if source is not None else None,
        gc_name=source.gc_name if source is not None else None,
        drawing_set_id=source.drawing_set_id if source is not None else None,
        version_label=source.version_label if source is not None else None,
        due_at=lead.due_at,
    )
    _apply_create_fields(est, data, lead)
    db.session.add(est)
    db.session.flush()

    if source is not None:
        for line in takeoff_lines_for_estimate(source.id):
            db.session.add(
                _copy_takeoff_line(line, estimate_id=est.id, lead_estimate_id=lead.id)
            )

    has_current = db.session.scalar(
        select(Estimate.id).where(
            Estimate.lead_estimate_id == lead.id,
            Estimate.is_current.is_(True),
            Estimate.id != est.id,
        )
    )
    if make_current or has_current is None:
        mark_current(est)
    db.session.flush()
    return est


def patch_estimate(est: Estimate, data: Mapping[str, Any]) -> Estimate:
    if estimate_is_locked(est):
        raise EstimateError(
            estimate_locked_payload()["error"],
            status=403,
            error_code="ESTIMATE_LOCKED",
        )
    if "name" in data or "title" in data:
        name = str(data.get("name") if "name" in data else data.get("title") or "").strip()[:255]
        if not name:
            raise EstimateError("name is required")
        est.name = name
        est.title = name
    if "version_label" in data:
        vl = data.get("version_label")
        est.version_label = str(vl).strip()[:64] or None if vl is not None else None
    if "gc_name" in data:
        gn = data.get("gc_name")
        est.gc_name = str(gn).strip()[:255] or None if gn is not None else None
    if "gc_company_id" in data:
        est.gc_company_id = _resolve_gc_company(data.get("gc_company_id"))
    if "drawing_set_id" in data:
        est.drawing_set_id = _resolve_drawing_set(data.get("drawing_set_id"), est.lead_estimate_id)
    if "fee_percentage" in data:
        est.fee_percentage = _decimal_or_zero(data.get("fee_percentage"))
    if "profit_margin" in data:
        est.profit_margin = _decimal_or_none(data.get("profit_margin"))
    if "rom" in data:
        est.rom = _decimal_or_none(data.get("rom"))
    if "notes" in data:
        n = data.get("notes")
        est.notes = str(n) if n is not None else None
    if "status" in data and data["status"] is not None:
        est.status = normalize_status(data.get("status"))
    if "is_current" in data and data["is_current"]:
        mark_current(est)
    return est


def delete_estimate(est: Estimate) -> None:
    if estimate_is_locked(est):
        raise EstimateError("cannot delete a locked estimate", status=400, error_code="ESTIMATE_LOCKED")
    if normalize_status(est.status) == "awarded":
        raise EstimateError("cannot delete an awarded estimate")
    lead_id = est.lead_estimate_id
    was_current = bool(est.is_current)
    db.session.delete(est)
    db.session.flush()
    if lead_id and was_current:
        nxt = db.session.scalar(
            select(Estimate)
            .where(Estimate.lead_estimate_id == lead_id)
            .order_by(Estimate.created_at.desc(), Estimate.id.desc())
        )
        if nxt is not None:
            mark_current(nxt)
        else:
            lead = db.session.get(LeadEstimate, lead_id)
            if lead is not None:
                lead.primary_estimate_id = None


def lock_estimate(est: Estimate) -> Estimate:
    if estimate_is_locked(est):
        raise EstimateError("estimate already locked")
    now = datetime.now(timezone.utc)
    est.estimate_locked_at = now
    _sync_lead_lock(est, locked_at=now)
    return est


def approve_estimate(est: Estimate, *, user_id: uuid.UUID | None = None) -> Estimate:
    if est.approved_at is not None:
        raise EstimateError("estimate already approved")
    if estimate_is_locked(est):
        raise EstimateError("estimate is locked; unlock before approving")
    now = datetime.now(timezone.utc)
    est.approved_at = now
    est.estimate_locked_at = now
    if normalize_status(est.status) == "draft":
        est.status = "submitted"
    _sync_lead_lock(est, locked_at=now, approved_at=now, approved_by=user_id)
    return est


def unlock_estimate(est: Estimate) -> Estimate:
    if not estimate_is_locked(est):
        raise EstimateError("estimate is not locked")
    est.estimate_locked_at = None
    _sync_lead_lock(est, locked_at=None)
    return est


def _sync_lead_lock(
    est: Estimate,
    *,
    locked_at: datetime | None,
    approved_at: datetime | None | object = ...,
    approved_by: uuid.UUID | None | object = ...,
) -> None:
    if est.lead_estimate_id is None:
        return
    current = current_estimate_for_lead(db.session.get(LeadEstimate, est.lead_estimate_id))
    if current is None or current.id != est.id:
        return
    lead = db.session.get(LeadEstimate, est.lead_estimate_id)
    if lead is None:
        return
    lead.estimate_locked_at = locked_at
    if approved_at is not ...:
        lead.estimate_approved_at = approved_at  # type: ignore[assignment]
    if approved_by is not ...:
        lead.estimate_approved_by_user_id = approved_by  # type: ignore[assignment]


def list_estimates_for_lead(lead: LeadEstimate) -> list[Estimate]:
    return list(
        db.session.scalars(
            select(Estimate)
            .where(Estimate.lead_estimate_id == lead.id)
            .options(joinedload(Estimate.gc_company), joinedload(Estimate.drawing_set))
            .order_by(Estimate.created_at.desc(), Estimate.id.desc())
        ).all()
    )


def create_drawing_set(lead: LeadEstimate, data: Mapping[str, Any]) -> DrawingSet:
    name = str(data.get("name") or "").strip()[:255]
    if not name:
        raise EstimateError("name is required")
    issued = data.get("issued_date")
    issued_date = None
    if issued:
        try:
            issued_date = date.fromisoformat(str(issued)[:10])
        except ValueError as exc:
            raise EstimateError("invalid issued_date") from exc
    notes = data.get("notes")
    row = DrawingSet(
        lead_estimate_id=lead.id,
        name=name,
        issued_date=issued_date,
        notes=str(notes) if notes is not None else None,
    )
    db.session.add(row)
    db.session.flush()
    return row


def list_drawing_sets(lead: LeadEstimate) -> list[DrawingSet]:
    return list(
        db.session.scalars(
            select(DrawingSet)
            .where(DrawingSet.lead_estimate_id == lead.id)
            .order_by(DrawingSet.created_at.desc())
        ).all()
    )


def lead_snapshot(lead: LeadEstimate) -> dict[str, Any]:
    return lead_estimate_public(lead)


def created_by_email(user_id: uuid.UUID | None) -> str | None:
    if user_id is None:
        return None
    user = db.session.get(User, user_id)
    return user.email if user is not None else None
