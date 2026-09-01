"""RFP body: narrative, takeoff attach, drawings, award, compare, freeze."""
from __future__ import annotations

import hashlib
import io
import secrets
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Mapping
from uuid import UUID

from sqlalchemy import func, or_, select

from ..extensions import db
from ..models import (
    AuditLog,
    Company,
    Contact,
    Document,
    Drawing,
    Estimate,
    EstimateLineItem,
    Rfp,
    RfpDrawing,
    RfpLineItem,
    RfpVendorQuote,
    TakeoffLineItem,
)
from ..services.object_storage import UploadCategory, read_stored_bytes, save_upload, send_stored_file
from ._rfi_service import ApiError, _iso, _parse_uuid

RFP_UNITS = ("SF", "LF", "SY", "EA", "LS", "HR", "GAL", "SQ")
OPEN_RFP_STATUSES = frozenset({"Draft", "Sent", "Partial", "Received"})
VENDOR_COMPANY_TYPES = frozenset({"vendor", "subcontractor", "other"})
_CAD_EXT = frozenset({".dwg", ".rvt", ".dxf", ".ifc"})
_GRAPH_ATTACH_MAX = 2_800_000


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def is_draft(rfp: Rfp) -> bool:
    return (rfp.status or "Draft") == "Draft" and rfp.sent_at is None


def assert_draft(rfp: Rfp) -> None:
    if not is_draft(rfp):
        raise ApiError("RFP is frozen after Send. Clone to a new RFP to change scope or lines.")


def _as_decimal(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        return Decimal(str(raw))
    except (InvalidOperation, ValueError):
        raise ApiError("invalid number")


def _qty_float(q: Decimal | None) -> float | None:
    if q is None:
        return None
    return float(q)


def load_rfp(rfp_id: uuid.UUID) -> Rfp:
    r = db.session.get(Rfp, rfp_id)
    if r is None:
        raise ApiError("rfp not found", 404)
    return r


def visible_line_items(rfp: Rfp) -> list[RfpLineItem]:
    if not rfp.show_line_table or (rfp.line_source or "") == "narrative":
        return []
    rows = db.session.scalars(
        select(RfpLineItem)
        .where(RfpLineItem.rfp_id == rfp.id, RfpLineItem.hidden_from_vendor.is_(False))
        .order_by(RfpLineItem.sort_order, RfpLineItem.created_at)
    ).all()
    return list(rows)


def all_line_items(rfp: Rfp) -> list[RfpLineItem]:
    return list(
        db.session.scalars(
            select(RfpLineItem).where(RfpLineItem.rfp_id == rfp.id).order_by(RfpLineItem.sort_order, RfpLineItem.created_at)
        ).all()
    )


def serialize_line(x: RfpLineItem, *, staff: bool = True) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(x.id),
        "description": x.description,
        "quantity": _qty_float(x.quantity),
        "unit": x.unit,
        "notes": x.notes,
        "csi_division": x.csi_division,
        "trade": x.trade,
        "room_area": x.room_area,
        "drawing_id": str(x.drawing_id) if x.drawing_id else None,
        "sort_order": x.sort_order,
        "hidden_from_vendor": bool(x.hidden_from_vendor),
    }
    if staff:
        out["source_kind"] = x.source_kind
        out["source_takeoff_line_id"] = str(x.source_takeoff_line_id) if x.source_takeoff_line_id else None
        out["product_snapshot"] = x.product_snapshot
    return out


def serialize_drawing_row(row: RfpDrawing, drawing: Drawing | None = None) -> dict[str, Any]:
    d = drawing or (db.session.get(Drawing, row.drawing_id) if row.drawing_id else None)
    doc = db.session.get(Document, row.document_id) if row.document_id else None
    filename = ""
    if d is not None:
        filename = (d.original_filename or d.sheet_number or d.title or "drawing.pdf")[:200]
    elif doc is not None:
        filename = (doc.original_filename or doc.title or "document.pdf")[:200]
    return {
        "id": str(row.id),
        "drawing_id": str(row.drawing_id) if row.drawing_id else None,
        "document_id": str(row.document_id) if row.document_id else None,
        "delivery": row.delivery,
        "include_on_portal": bool(row.include_on_portal),
        "sort_order": row.sort_order,
        "frozen_pdf_path": row.frozen_pdf_path,
        "frozen_bytes": row.frozen_bytes,
        "sheet_number": d.sheet_number if d is not None else None,
        "sheet_title": (d.sheet_title or d.title) if d is not None else (doc.title if doc else None),
        "discipline": d.discipline if d is not None else None,
        "revision": d.revision if d is not None else None,
        "updated_at": _iso(d.updated_at) if d is not None else (_iso(doc.updated_at) if doc else None),
        "filename": filename,
        "is_cad": _is_cad(d or doc),
        "has_pdf": bool(row.frozen_pdf_path) or _has_pdf_rendition(d or doc),
    }


def _is_cad(obj: Drawing | Document | None) -> bool:
    if obj is None:
        return False
    name = (getattr(obj, "original_filename", None) or getattr(obj, "title", None) or "").lower()
    mime = (getattr(obj, "mime_type", None) or "").lower()
    return any(name.endswith(ext) for ext in _CAD_EXT) or "dwg" in mime or "revit" in mime


def _has_pdf_rendition(obj: Drawing | Document | None) -> bool:
    if obj is None:
        return False
    name = (getattr(obj, "original_filename", None) or "").lower()
    mime = (getattr(obj, "mime_type", None) or "").lower()
    if mime.startswith("application/pdf") or name.endswith(".pdf"):
        return True
    if isinstance(obj, Drawing):
        return not _is_cad(obj)
    return False


def rfp_closed(rfp: Rfp) -> bool:
    if (rfp.status or "") in ("Awarded", "Closed"):
        return True
    if rfp.due_at is None:
        return False
    due = rfp.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return _utcnow() > due


def content_ready(rfp: Rfp) -> tuple[bool, list[str], list[str]]:
    """Return (ok, blocking errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []
    visible = visible_line_items(rfp)
    scope = (rfp.scope_of_work or "").strip()
    if not visible and not scope:
        errors.append("Add at least one line item or a scope of work before sending.")
    if not (rfp.inclusions or "").strip() and not (rfp.exclusions or "").strip():
        warnings.append("Inclusions and exclusions are both empty.")
    if rfp.due_at is None:
        errors.append("Set a due date before sending.")
    if rfp.project_id is None and rfp.lead_estimate_id is None:
        errors.append("Link a project (or bid) before sending.")
    return not errors, errors, warnings


def default_line_source(project_id: uuid.UUID | None, lead_estimate_id: uuid.UUID | None) -> str:
    q = select(func.count()).select_from(TakeoffLineItem)
    if project_id:
        q = q.where(
            or_(
                TakeoffLineItem.project_id == project_id,
                TakeoffLineItem.estimate_id.in_(select(Estimate.id).where(Estimate.project_id == project_id)),
            )
        )
    elif lead_estimate_id:
        q = q.where(
            or_(
                TakeoffLineItem.lead_estimate_id == lead_estimate_id,
                TakeoffLineItem.estimate_id.in_(
                    select(Estimate.id).where(Estimate.lead_estimate_id == lead_estimate_id)
                ),
            )
        )
    else:
        return "manual"
    n = db.session.scalar(q) or 0
    return "takeoff" if int(n) > 0 else "manual"


def apply_line_source(rfp: Rfp, source: str, *, confirm: bool = False) -> None:
    src = (source or "").strip().lower()
    if src not in ("takeoff", "manual", "narrative"):
        raise ApiError("line_source must be takeoff, manual, or narrative")
    prev = (rfp.line_source or "manual").lower()
    if src == prev:
        rfp.show_line_table = src != "narrative"
        return
    lines = all_line_items(rfp)
    if prev in ("takeoff",) and src == "manual":
        if lines and not confirm:
            raise ApiError("Confirm converting takeoff rows to manual items.", 409)
        for ln in lines:
            ln.source_takeoff_line_id = None
            ln.source_kind = "manual"
        rfp.source_estimate_id = None
        rfp.show_line_table = True
    elif src == "narrative":
        if lines and not confirm:
            raise ApiError("Hide these lines from vendors? Lines are kept on the RFP but not shown until you switch back.", 409)
        for ln in lines:
            ln.hidden_from_vendor = True
        rfp.show_line_table = False
    else:
        for ln in lines:
            ln.hidden_from_vendor = False
        rfp.show_line_table = True
    rfp.line_source = src


def patch_rfp(rfp: Rfp, data: Mapping[str, Any], *, confirm_source: bool = False) -> Rfp:
    assert_draft(rfp)
    if "title" in data:
        rfp.title = str(data.get("title") or rfp.title or "RFP")[:500]
    if "due_at" in data:
        from ._rfi_service import _parse_dt

        rfp.due_at = _parse_dt(data.get("due_at"))
    for field in ("scope_of_work", "inclusions", "exclusions", "clarifications"):
        if field in data:
            raw = data.get(field)
            setattr(rfp, field, (str(raw).strip() or None) if raw is not None else None)
    if "cc_estimator" in data:
        rfp.cc_estimator = bool(data.get("cc_estimator"))
    if "show_line_table" in data and "line_source" not in data:
        rfp.show_line_table = bool(data.get("show_line_table"))
    if "line_source" in data:
        apply_line_source(rfp, str(data.get("line_source") or ""), confirm=confirm_source or bool(data.get("confirm")))
    if "source_estimate_id" in data:
        eid = _parse_uuid(data.get("source_estimate_id"))
        rfp.source_estimate_id = eid
    db.session.flush()
    return rfp


def _product_snapshot_from_takeoff(tl: TakeoffLineItem) -> Any | None:
    md = tl.measurement_data
    if not isinstance(md, dict):
        return None
    if "product_snapshot" in md:
        return md.get("product_snapshot")
    keys = {str(k).lower() for k in md}
    if keys & {"sku", "config", "product", "locker", "penco", "catalog"}:
        return md
    return None


def copy_takeoff_to_line(rfp: Rfp, tl: TakeoffLineItem, sort_order: int) -> RfpLineItem:
    existing = db.session.scalar(
        select(RfpLineItem).where(
            RfpLineItem.rfp_id == rfp.id,
            RfpLineItem.source_takeoff_line_id == tl.id,
        )
    )
    row = existing or RfpLineItem(rfp_id=rfp.id)
    row.description = (tl.description or "")[:500]
    row.quantity = tl.quantity
    row.unit = (tl.unit or "EA")[:50]
    row.notes = tl.notes
    row.csi_division = (tl.section or tl.job_cost_code or None)
    row.trade = tl.line_role or tl.cost_type
    row.room_area = tl.takeoff_location
    row.drawing_id = tl.drawing_id
    row.source_takeoff_line_id = tl.id
    row.source_kind = "takeoff"
    row.hidden_from_vendor = False
    row.product_snapshot = _product_snapshot_from_takeoff(tl)
    row.sort_order = sort_order
    if existing is None:
        db.session.add(row)
    return row


def remaining_takeoff_ids(estimate_id: uuid.UUID) -> set[uuid.UUID]:
    lines = db.session.scalars(
        select(TakeoffLineItem).where(TakeoffLineItem.estimate_id == estimate_id)
    ).all()
    awarded = {
        x.takeoff_line_item_id
        for x in db.session.scalars(
            select(EstimateLineItem).where(
                EstimateLineItem.estimate_id == estimate_id,
                EstimateLineItem.vendor_quote.is_not(None),
            )
        ).all()
    }
    on_open = set(
        db.session.scalars(
            select(RfpLineItem.source_takeoff_line_id)
            .join(Rfp, Rfp.id == RfpLineItem.rfp_id)
            .where(
                RfpLineItem.source_takeoff_line_id.is_not(None),
                Rfp.status.in_(tuple(OPEN_RFP_STATUSES)),
            )
        ).all()
    )
    remaining: set[uuid.UUID] = set()
    for tl in lines:
        if tl.id in awarded:
            continue
        if tl.id in on_open:
            continue
        remaining.add(tl.id)
    return remaining


def list_takeoff_candidates(rfp: Rfp, estimate_id: uuid.UUID | None) -> dict[str, Any]:
    estimates: list[Estimate] = []
    if rfp.project_id:
        estimates = list(
            db.session.scalars(
                select(Estimate).where(Estimate.project_id == rfp.project_id).order_by(Estimate.updated_at.desc())
            ).all()
        )
    if rfp.lead_estimate_id:
        extra = list(
            db.session.scalars(
                select(Estimate)
                .where(Estimate.lead_estimate_id == rfp.lead_estimate_id)
                .order_by(Estimate.updated_at.desc())
            ).all()
        )
        seen = {e.id for e in estimates}
        for e in extra:
            if e.id not in seen:
                estimates.append(e)
    est_items = []
    for e in estimates:
        n = db.session.scalar(
            select(func.count()).select_from(TakeoffLineItem).where(TakeoffLineItem.estimate_id == e.id)
        ) or 0
        est_items.append(
            {
                "id": str(e.id),
                "name": e.name or e.title or "Estimate",
                "status": e.status,
                "updated_at": _iso(e.updated_at),
                "line_count": int(n),
            }
        )
    chosen = None
    if estimate_id:
        chosen = db.session.get(Estimate, estimate_id)
    elif rfp.source_estimate_id:
        chosen = db.session.get(Estimate, rfp.source_estimate_id)
    elif estimates:
        chosen = estimates[0]
    rows_out: list[dict[str, Any]] = []
    remaining: set[uuid.UUID] = set()
    if chosen is not None:
        remaining = remaining_takeoff_ids(chosen.id)
        on_this = {
            x.source_takeoff_line_id
            for x in all_line_items(rfp)
            if x.source_takeoff_line_id is not None
        }
        for tl in db.session.scalars(
            select(TakeoffLineItem).where(TakeoffLineItem.estimate_id == chosen.id).order_by(TakeoffLineItem.sort_order)
        ).all():
            rows_out.append(
                {
                    "id": str(tl.id),
                    "csi_division": tl.section or tl.job_cost_code,
                    "trade": tl.line_role or tl.cost_type,
                    "description": tl.description,
                    "quantity": float(tl.quantity) if tl.quantity is not None else None,
                    "unit": tl.unit,
                    "room_area": tl.takeoff_location,
                    "notes": tl.notes,
                    "remaining": tl.id in remaining,
                    "already_on_this_rfp": tl.id in on_this,
                }
            )
    return {
        "estimates": est_items,
        "estimate_id": str(chosen.id) if chosen is not None else None,
        "lines": rows_out,
        "has_estimates": bool(est_items),
    }


def attach_takeoff(rfp: Rfp, data: Mapping[str, Any]) -> dict[str, Any]:
    assert_draft(rfp)
    eid = _parse_uuid(data.get("estimate_id") or rfp.source_estimate_id)
    if not eid:
        raise ApiError("estimate_id is required")
    est = db.session.get(Estimate, eid)
    if est is None:
        raise ApiError("estimate not found", 404)
    remaining_only = bool(data.get("remaining") or data.get("select_remaining"))
    ids_raw = data.get("takeoff_line_ids") or data.get("line_ids") or []
    chosen: list[TakeoffLineItem]
    if remaining_only:
        remaining = remaining_takeoff_ids(eid)
        if remaining:
            chosen = list(
                db.session.scalars(
                    select(TakeoffLineItem)
                    .where(TakeoffLineItem.estimate_id == eid, TakeoffLineItem.id.in_(tuple(remaining)))
                    .order_by(TakeoffLineItem.sort_order)
                ).all()
            )
        else:
            chosen = []
    elif isinstance(ids_raw, list) and ids_raw:
        wanted = [_parse_uuid(x) for x in ids_raw]
        wanted = [x for x in wanted if x]
        chosen = list(
            db.session.scalars(
                select(TakeoffLineItem)
                .where(TakeoffLineItem.estimate_id == eid, TakeoffLineItem.id.in_(wanted))
                .order_by(TakeoffLineItem.sort_order)
            ).all()
        )
    else:
        raise ApiError("takeoff_line_ids is required (or remaining=true)")
    max_sort = db.session.scalar(
        select(func.coalesce(func.max(RfpLineItem.sort_order), -1)).where(RfpLineItem.rfp_id == rfp.id)
    )
    next_sort = int(max_sort if max_sort is not None else -1) + 1
    attached = 0
    for tl in chosen:
        copy_takeoff_to_line(rfp, tl, next_sort)
        next_sort += 1
        attached += 1
    rfp.source_estimate_id = eid
    rfp.line_source = "takeoff"
    rfp.show_line_table = True
    for ln in all_line_items(rfp):
        ln.hidden_from_vendor = False
    db.session.flush()
    return {
        "attached": attached,
        "estimate_id": str(eid),
        "estimate_name": est.name or est.title or "Estimate",
    }


def refresh_takeoff(rfp: Rfp) -> dict[str, Any]:
    assert_draft(rfp)
    refreshed = 0
    for ln in all_line_items(rfp):
        if not ln.source_takeoff_line_id:
            continue
        tl = db.session.get(TakeoffLineItem, ln.source_takeoff_line_id)
        if tl is None:
            continue
        copy_takeoff_to_line(rfp, tl, ln.sort_order)
        refreshed += 1
    db.session.flush()
    return {"refreshed": refreshed}


def upsert_line(rfp: Rfp, data: Mapping[str, Any], line_id: uuid.UUID | None = None) -> RfpLineItem:
    assert_draft(rfp)
    row = db.session.get(RfpLineItem, line_id) if line_id else None
    if line_id and row is None:
        raise ApiError("line item not found", 404)
    if row is None:
        row = RfpLineItem(rfp_id=rfp.id, source_kind="manual")
        db.session.add(row)
    desc = str(data.get("description") if "description" in data else (row.description or "")).strip()
    if not desc:
        raise ApiError("description is required")
    row.description = desc[:500]
    if "unit" in data or row.unit is None:
        unit = str(data.get("unit") or row.unit or "EA").strip().upper()[:50] or "EA"
        row.unit = unit
    if "quantity" in data:
        qty = _as_decimal(data.get("quantity"))
        if qty is None and (row.unit or "").upper() != "LS":
            desc_l = (row.description or "").lower()
            if "allowance" not in desc_l and "quote to spec" not in desc_l:
                raise ApiError("quantity is required unless unit is LS or the line is an allowance")
        row.quantity = qty
    elif row.quantity is None and (row.unit or "").upper() != "LS":
        row.quantity = Decimal("0")
    if "notes" in data:
        row.notes = (str(data.get("notes") or "").strip() or None)
    if "csi_division" in data:
        row.csi_division = (str(data.get("csi_division") or "").strip() or None)
    if "trade" in data:
        row.trade = (str(data.get("trade") or "").strip() or None)
    if "room_area" in data:
        row.room_area = (str(data.get("room_area") or "").strip() or None)
    if "drawing_id" in data:
        row.drawing_id = _parse_uuid(data.get("drawing_id"))
    if "sort_order" in data:
        try:
            row.sort_order = int(data.get("sort_order") or 0)
        except (TypeError, ValueError):
            row.sort_order = 0
    if "hidden_from_vendor" in data:
        row.hidden_from_vendor = bool(data.get("hidden_from_vendor"))
    if not row.source_kind:
        row.source_kind = "manual"
    db.session.flush()
    return row


def delete_line(rfp: Rfp, line_id: uuid.UUID) -> None:
    assert_draft(rfp)
    row = db.session.get(RfpLineItem, line_id)
    if row is None or row.rfp_id != rfp.id:
        raise ApiError("line item not found", 404)
    db.session.delete(row)
    db.session.flush()


def list_drawing_candidates(rfp: Rfp) -> dict[str, Any]:
    pid = rfp.project_id
    drawings: list[Drawing] = []
    if pid:
        drawings = list(
            db.session.scalars(
                select(Drawing)
                .where(Drawing.project_id == pid)
                .order_by(Drawing.sheet_number.asc().nullslast(), Drawing.updated_at.desc())
            ).all()
        )
    docs: list[Document] = []
    if pid and not drawings:
        docs = list(
            db.session.scalars(
                select(Document).where(
                    Document.project_id == pid,
                    Document.document_type.in_(("specification", "other")),
                )
            ).all()
        )
        docs = [
            d
            for d in docs
            if "draw" in (d.title or "").lower()
            or "spec" in (d.title or "").lower()
            or (d.original_filename or "").lower().endswith(".pdf")
        ]
    referenced = {x.drawing_id for x in all_line_items(rfp) if x.drawing_id}
    selected = {
        (row.drawing_id, row.document_id): row
        for row in db.session.scalars(select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id)).all()
    }
    items = []
    for d in drawings:
        sel = selected.get((d.id, None))
        items.append(
            {
                "drawing_id": str(d.id),
                "document_id": None,
                "sheet_number": d.sheet_number,
                "sheet_title": d.sheet_title or d.title,
                "discipline": d.discipline,
                "revision": d.revision,
                "updated_at": _iso(d.updated_at),
                "filename": d.original_filename or d.title,
                "is_cad": _is_cad(d),
                "has_pdf": _has_pdf_rendition(d),
                "prechecked": d.id in referenced or sel is not None,
                "delivery": sel.delivery if sel is not None else "link",
            }
        )
    for doc in docs:
        if getattr(doc, "document_type", None) == "drawing":
            continue
        sel = selected.get((None, doc.id))
        items.append(
            {
                "drawing_id": None,
                "document_id": str(doc.id),
                "sheet_number": None,
                "sheet_title": doc.title,
                "discipline": None,
                "revision": None,
                "updated_at": _iso(doc.updated_at),
                "filename": doc.original_filename or doc.title,
                "is_cad": _is_cad(doc),
                "has_pdf": _has_pdf_rendition(doc),
                "prechecked": sel is not None,
                "delivery": sel.delivery if sel is not None else "link",
            }
        )
    return {"items": items, "selected": [serialize_drawing_row(r) for r in selected.values()]}


def replace_drawings(rfp: Rfp, data: Mapping[str, Any]) -> list[RfpDrawing]:
    assert_draft(rfp)
    raw = data.get("drawings") or data.get("items") or []
    if not isinstance(raw, list):
        raise ApiError("drawings must be a list")
    existing = list(db.session.scalars(select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id)).all())
    for row in existing:
        db.session.delete(row)
    db.session.flush()
    out: list[RfpDrawing] = []
    for i, item in enumerate(raw):
        if not isinstance(item, Mapping):
            continue
        did = _parse_uuid(item.get("drawing_id"))
        doc_id = _parse_uuid(item.get("document_id"))
        if not did and not doc_id:
            continue
        delivery = str(item.get("delivery") or "link").strip().lower()
        if delivery not in ("link", "attach", "both"):
            delivery = "link"
        obj = db.session.get(Drawing, did) if did else db.session.get(Document, doc_id)
        if _is_cad(obj) and delivery in ("attach", "both"):
            delivery = "link"
        row = RfpDrawing(
            rfp_id=rfp.id,
            drawing_id=did,
            document_id=doc_id,
            delivery=delivery,
            include_on_portal=bool(item.get("include_on_portal", True)),
            sort_order=int(item.get("sort_order") or i),
        )
        db.session.add(row)
        out.append(row)
    db.session.flush()
    return out


def _drawing_pdf_bytes(drawing: Drawing | None, document: Document | None = None) -> tuple[bytes | None, str]:
    from ..services.project_file_keys import document_object_candidates, drawing_object_candidates

    if drawing is not None:
        for name in drawing_object_candidates(drawing):
            data = read_stored_bytes(UploadCategory.DRAWINGS, name)
            if data:
                fname = drawing.original_filename or f"{drawing.sheet_number or drawing.id}.pdf"
                return data, fname
    if document is not None:
        for name in document_object_candidates(document):
            data = read_stored_bytes(UploadCategory.DOCUMENTS, name)
            if data:
                return data, document.original_filename or f"{document.id}.pdf"
    return None, ""


def freeze_drawings_on_send(rfp: Rfp) -> None:
    rows = db.session.scalars(select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id)).all()
    for row in rows:
        if row.frozen_pdf_path:
            continue
        drawing = db.session.get(Drawing, row.drawing_id) if row.drawing_id else None
        document = db.session.get(Document, row.document_id) if row.document_id else None
        if _is_cad(drawing or document):
            continue
        data, _fname = _drawing_pdf_bytes(drawing, document)
        if not data:
            continue
        digest = hashlib.sha256(data).hexdigest()
        object_name = f"rfp-snapshots/{rfp.id}/{row.id}.pdf"
        save_upload(UploadCategory.DOCUMENTS, object_name, io.BytesIO(data))
        row.frozen_pdf_path = object_name
        row.frozen_checksum = digest
        row.frozen_bytes = len(data)
    db.session.flush()


def attachment_plan(rfp: Rfp, *, include_attachments: bool = True, graph_limit: bool = False) -> dict[str, Any]:
    """Decide which sheets attach vs link, applying the size cap (largest-first drop)."""
    from flask import current_app

    max_mb = 18
    try:
        max_mb = int(current_app.config.get("RFP_MAIL_MAX_ATTACH_MB") or 18)
    except (TypeError, ValueError, RuntimeError):
        max_mb = 18
    cap = max(1, max_mb) * 1024 * 1024
    rows = list(
        db.session.scalars(
            select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id).order_by(RfpDrawing.sort_order)
        ).all()
    )
    attach_candidates: list[tuple[RfpDrawing, bytes, str, int]] = []
    link_only: list[RfpDrawing] = []
    for row in rows:
        want_attach = include_attachments and row.delivery in ("attach", "both")
        drawing = db.session.get(Drawing, row.drawing_id) if row.drawing_id else None
        document = db.session.get(Document, row.document_id) if row.document_id else None
        if _is_cad(drawing or document):
            link_only.append(row)
            continue
        data, fname = _drawing_pdf_bytes(drawing, document)
        if row.frozen_pdf_path:
            frozen = read_stored_bytes(UploadCategory.DOCUMENTS, row.frozen_pdf_path)
            if frozen:
                data = frozen
        if not data or not want_attach:
            link_only.append(row)
            continue
        if not (fname or "").lower().endswith(".pdf") and not (data[:5] == b"%PDF-" or data[:4] == b"%PDF"):
            link_only.append(row)
            continue
        if graph_limit and len(data) > _GRAPH_ATTACH_MAX:
            link_only.append(row)
            continue
        attach_candidates.append((row, data, fname if fname.lower().endswith(".pdf") else f"{fname}.pdf", len(data)))
    attach_candidates.sort(key=lambda t: t[3], reverse=True)
    attached: list[tuple[RfpDrawing, bytes, str]] = []
    used = 0
    overflow: list[RfpDrawing] = []
    keep: list[tuple[RfpDrawing, bytes, str, int]] = []
    for item in reversed(attach_candidates):
        if used + item[3] <= cap:
            keep.append(item)
            used += item[3]
        else:
            overflow.append(item[0])
    for item in keep:
        attached.append((item[0], item[1], item[2]))
    for row in overflow:
        link_only.append(row)
    warning = None
    if overflow:
        warning = (
            f"{len(attached)} sheet(s) will be attached ({used / (1024 * 1024):.1f} MB). "
            f"{len(overflow)} sheet(s) over the cap will be links only."
        )
    elif attached:
        warning = f"{len(attached)} sheet(s) will be attached ({used / (1024 * 1024):.1f} MB)."
    return {
        "attached": attached,
        "link_rows": link_only + [r for r, *_ in attached if r.delivery in ("link", "both") or True],
        "all_rows": rows,
        "attach_bytes": used,
        "warning": warning,
        "overflow_ids": [str(r.id) for r in overflow],
    }


def drawing_download_bytes(row: RfpDrawing) -> tuple[bytes | None, str]:
    if row.frozen_pdf_path:
        data = read_stored_bytes(UploadCategory.DOCUMENTS, row.frozen_pdf_path)
        if data:
            return data, f"{row.id}.pdf"
    drawing = db.session.get(Drawing, row.drawing_id) if row.drawing_id else None
    document = db.session.get(Document, row.document_id) if row.document_id else None
    return _drawing_pdf_bytes(drawing, document)


def stream_frozen_or_live(row: RfpDrawing):
    data, fname = drawing_download_bytes(row)
    if data is None:
        return None
    if row.frozen_pdf_path:
        return send_stored_file(
            UploadCategory.DOCUMENTS,
            row.frozen_pdf_path,
            mimetype="application/pdf",
            download_name=fname or "drawing.pdf",
        )
    return None, data, fname


def vendor_directory(rfp: Rfp, *, q: str = "", trade: str = "") -> list[dict[str, Any]]:
    stmt = (
        select(Company)
        .where(Company.deleted_at.is_(None), Company.company_type.in_(tuple(VENDOR_COMPANY_TYPES)))
        .order_by(Company.name.asc())
        .limit(400)
    )
    rows = list(db.session.scalars(stmt).all())
    needle = (q or "").strip().lower()
    trade_n = (trade or "").strip().lower()
    out = []
    for c in rows:
        if needle and needle not in (c.name or "").lower():
            continue
        specialties = c.trade_specialties
        trade_blob = ""
        if isinstance(specialties, dict):
            trade_blob = " ".join(str(v) for v in specialties.values()).lower()
        elif isinstance(specialties, list):
            trade_blob = " ".join(str(v) for v in specialties).lower()
        elif specialties:
            trade_blob = str(specialties).lower()
        if trade_n and trade_blob and trade_n not in trade_blob and trade_n not in (c.name or "").lower():
            continue
        contacts = list(
            db.session.scalars(
                select(Contact).where(Contact.company_id == c.id).order_by(Contact.is_primary.desc())
            ).all()
        )
        email = (c.email or "").strip()
        primary = next((ct for ct in contacts if ct.is_primary and (ct.email or "").strip()), None)
        if primary is not None:
            email = (primary.email or email).strip()
        if not email:
            with_email = next((ct for ct in contacts if (ct.email or "").strip()), None)
            if with_email is not None:
                email = (with_email.email or "").strip()
        out.append(
            {
                "id": str(c.id),
                "name": c.name,
                "company_type": c.company_type,
                "email": email or None,
                "missing_email": not bool(email),
                "company_edit_url": f"usis-companies.html?id={c.id}",
                "trade_specialties": specialties,
                "contacts": [
                    {
                        "id": str(ct.id),
                        "name": " ".join(p for p in (ct.first_name or "", ct.last_name or "") if p).strip() or c.name,
                        "email": (ct.email or "").strip() or None,
                        "title": ct.title,
                        "is_primary": bool(ct.is_primary),
                    }
                    for ct in contacts
                ],
            }
        )
    return out


def clone_rfp(rfp: Rfp) -> Rfp:
    token = secrets.token_urlsafe(32)[:64]
    clone = Rfp(
        lead_estimate_id=rfp.lead_estimate_id,
        project_id=rfp.project_id,
        title=((rfp.title or "RFP") + " (clone)")[:500],
        status="Draft",
        due_at=rfp.due_at,
        public_token=token,
        line_source=rfp.line_source or "manual",
        source_estimate_id=rfp.source_estimate_id,
        scope_of_work=rfp.scope_of_work,
        inclusions=rfp.inclusions,
        exclusions=rfp.exclusions,
        clarifications=rfp.clarifications,
        show_line_table=bool(rfp.show_line_table),
        cc_estimator=bool(rfp.cc_estimator),
    )
    db.session.add(clone)
    db.session.flush()
    for ln in all_line_items(rfp):
        db.session.add(
            RfpLineItem(
                rfp_id=clone.id,
                sort_order=ln.sort_order,
                description=ln.description,
                quantity=ln.quantity,
                unit=ln.unit,
                notes=ln.notes,
                csi_division=ln.csi_division,
                trade=ln.trade,
                room_area=ln.room_area,
                drawing_id=ln.drawing_id,
                source_takeoff_line_id=ln.source_takeoff_line_id,
                source_kind=ln.source_kind,
                hidden_from_vendor=ln.hidden_from_vendor,
                product_snapshot=ln.product_snapshot,
            )
        )
    for dr in db.session.scalars(select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id)).all():
        db.session.add(
            RfpDrawing(
                rfp_id=clone.id,
                drawing_id=dr.drawing_id,
                document_id=dr.document_id,
                delivery=dr.delivery,
                include_on_portal=dr.include_on_portal,
                sort_order=dr.sort_order,
            )
        )
    db.session.flush()
    return clone


def award_rfp(rfp: Rfp, data: Mapping[str, Any], *, user_id: UUID | None) -> dict[str, Any]:
    qid = _parse_uuid(data.get("quote_id") or data.get("vendor_quote_id"))
    if not qid:
        raise ApiError("quote_id is required")
    quote = db.session.get(RfpVendorQuote, qid)
    if quote is None or quote.rfp_id != rfp.id:
        raise ApiError("quote not found", 404)
    prices = quote.line_prices if isinstance(quote.line_prices, list) else []
    price_by_line: dict[str, Decimal] = {}
    if isinstance(quote.line_prices, dict):
        for k, v in quote.line_prices.items():
            if isinstance(v, Mapping) and v.get("unit_price") is not None:
                price_by_line[str(k)] = _as_decimal(v.get("unit_price")) or Decimal("0")
            elif v is not None:
                price_by_line[str(k)] = _as_decimal(v) or Decimal("0")
    for item in prices:
        if not isinstance(item, Mapping):
            continue
        lid = str(item.get("line_id") or "")
        up = item.get("unit_price")
        if lid and up is not None:
            price_by_line[lid] = _as_decimal(up) or Decimal("0")
    updated = 0
    for ln in visible_line_items(rfp) or all_line_items(rfp):
        if not ln.source_takeoff_line_id:
            continue
        unit_price = price_by_line.get(str(ln.id))
        if unit_price is None and quote.lump_sum_amount is not None and len(visible_line_items(rfp)) <= 1:
            unit_price = quote.lump_sum_amount
        if unit_price is None:
            continue
        q_est = select(EstimateLineItem).where(EstimateLineItem.takeoff_line_item_id == ln.source_takeoff_line_id)
        if rfp.source_estimate_id:
            q_est = q_est.where(EstimateLineItem.estimate_id == rfp.source_estimate_id)
        eli = db.session.scalar(q_est)
        if eli is None:
            continue
        eli.vendor_quote = unit_price
        updated += 1
    rfp.status = "Awarded"
    db.session.add(
        AuditLog(
            user_id=user_id,
            entity_type="rfp",
            entity_id=rfp.id,
            action="award",
            changes={"quote_id": str(quote.id), "vendor_label": quote.vendor_label, "lines_updated": updated},
        )
    )
    db.session.commit()
    return {"item": {"id": str(rfp.id), "status": rfp.status, "awarded_quote_id": str(quote.id), "takeoff_updated": updated}}


def compare_table(rfp: Rfp) -> dict[str, Any]:
    quotes = list(
        db.session.scalars(
            select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == rfp.id).order_by(RfpVendorQuote.created_at)
        ).all()
    )
    vendors = [
        {
            "id": str(q.id),
            "vendor_label": q.vendor_label,
            "invited_email": q.invited_email,
            "lump_sum_amount": float(q.lump_sum_amount) if q.lump_sum_amount is not None else None,
            "received_at": _iso(q.received_at),
        }
        for q in quotes
    ]
    lines = visible_line_items(rfp)
    rows: list[dict[str, Any]] = []
    if not lines:
        prices: dict[str, float | None] = {}
        numeric: list[float] = []
        for q in quotes:
            val = float(q.lump_sum_amount) if q.lump_sum_amount is not None else None
            prices[str(q.id)] = val
            if val is not None:
                numeric.append(val)
        lowest = min(numeric) if numeric else None
        rows.append(
            {
                "line_id": None,
                "description": f"Lump sum — {rfp.title or 'RFP'}",
                "quantity": None,
                "unit": "LS",
                "prices": prices,
                "lowest": lowest,
            }
        )
    else:
        for ln in lines:
            prices = {}
            numeric = []
            for q in quotes:
                val = None
                lp = q.line_prices
                if isinstance(lp, dict):
                    cell = lp.get(str(ln.id)) or lp.get("lines", {}).get(str(ln.id)) if isinstance(lp.get("lines"), dict) else lp.get(str(ln.id))
                    if isinstance(cell, Mapping):
                        raw = cell.get("extension", cell.get("unit_price"))
                        val = float(raw) if raw is not None else None
                    elif cell is not None:
                        val = float(cell)
                elif isinstance(lp, list):
                    hit = next((x for x in lp if isinstance(x, Mapping) and str(x.get("line_id")) == str(ln.id)), None)
                    if hit is not None:
                        raw = hit.get("extension", hit.get("unit_price"))
                        val = float(raw) if raw is not None else None
                prices[str(q.id)] = val
                if val is not None:
                    numeric.append(val)
            rows.append(
                {
                    "line_id": str(ln.id),
                    "description": ln.description,
                    "quantity": _qty_float(ln.quantity),
                    "unit": ln.unit,
                    "prices": prices,
                    "lowest": min(numeric) if numeric else None,
                }
            )
    return {"vendors": vendors, "rows": rows, "line_source": rfp.line_source}


def log_send_audit(
    *,
    rfp: Rfp,
    quote: RfpVendorQuote,
    from_email: str,
    drawing_ids: Iterable[str],
    attach_bytes: int,
    message_id: str | None,
    user_id: UUID | None,
) -> None:
    db.session.add(
        AuditLog(
            user_id=user_id,
            entity_type="rfp",
            entity_id=rfp.id,
            action="send",
            changes={
                "rfp_id": str(rfp.id),
                "company_id": str(quote.vendor_company_id) if quote.vendor_company_id else None,
                "to_email": quote.invited_email,
                "from_email": from_email,
                "drawing_ids": list(drawing_ids),
                "attach_bytes": attach_bytes,
                "message_id": message_id,
            },
        )
    )
