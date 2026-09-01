"""Website order-by dates, supplier confirm notices, and field receive/delivery lists."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    Commitment,
    CommitmentLineItem,
    Company,
    Contact,
    CorrespondenceItem,
    Project,
    ProjectMaterialOrder,
    ProjectScheduleItem,
    PurchaseOrderReceipt,
    PurchaseOrderShipment,
)
from ._notifications import _graph_configured, _mail_from, send_plain_notification_email
from ._perms import CurrentUser, is_company_readonly
from ._rfi_service import ApiError, _parse_uuid

SUPPLIER_CONFIRM_NONE = "none"
SUPPLIER_CONFIRM_SENT = "sent"
SUPPLIER_CONFIRM_CONFIRMED = "confirmed"
CONFIRM_OVERDUE_DAYS = 2
FIELD_RECEIPT_CONDITIONS = frozenset({"accepted", "short", "damaged", "held_unapproved"})
SHIPPED_STATUSES = frozenset({"in_transit", "out_for_delivery", "delivered", "exception"})


def _can_view(cu: CurrentUser) -> bool:
    return True


def _can_mutate(cu: CurrentUser) -> bool:
    return not is_company_readonly(cu)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(d: date | datetime | None) -> str | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.isoformat()
    return d.isoformat()


def _dec(v: Any) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:
        return Decimal("0")


def compute_order_by_date(needed_on_site: date | None, lead_time_days: int | None) -> date | None:
    """Order-by = install start (needed on site) minus lead time on the PO."""
    if needed_on_site is None or lead_time_days is None:
        return None
    return needed_on_site - timedelta(days=int(lead_time_days))


def _effective_confirm_status(c: Commitment, *, today: date | None = None) -> str:
    status = (c.supplier_confirm_status or SUPPLIER_CONFIRM_NONE).strip() or SUPPLIER_CONFIRM_NONE
    if status != SUPPLIER_CONFIRM_SENT:
        return status
    sent = c.supplier_confirm_sent_at
    if sent is None:
        return status
    as_of = today or date.today()
    sent_day = sent.date() if isinstance(sent, datetime) else sent
    if as_of > sent_day + timedelta(days=CONFIRM_OVERDUE_DAYS):
        return "overdue"
    return status


def _vendor_contact_email(c: Commitment) -> str | None:
    if c.vendor_contact_id:
        contact = db.session.get(Contact, c.vendor_contact_id)
        if contact and contact.email:
            return contact.email.strip()
    vendor = c.vendor or db.session.get(Company, c.vendor_company_id)
    if vendor is None:
        return None
    primary = db.session.scalar(
        select(Contact)
        .where(Contact.company_id == vendor.id, Contact.email.is_not(None))
        .order_by(Contact.is_primary.desc(), Contact.created_at)
    )
    if primary and primary.email:
        return primary.email.strip()
    return None


def _load_schedule_item(project_id: uuid.UUID, item_id: uuid.UUID | None) -> ProjectScheduleItem | None:
    if item_id is None:
        return None
    return db.session.scalar(
        select(ProjectScheduleItem).where(
            ProjectScheduleItem.id == item_id,
            ProjectScheduleItem.project_id == project_id,
        )
    )


def apply_schedule_need_by(c: Commitment) -> ProjectScheduleItem | None:
    """When a PO is linked to a schedule line, needed-on-site is that line's start."""
    item = _load_schedule_item(c.project_id, c.schedule_item_id)
    if item is not None:
        c.needed_on_site_date = item.start_date
    return item


def sync_commitment_order_dates(c: Commitment) -> bool:
    """Recompute order-by. Returns True when the issued PO's order-by moved."""
    apply_schedule_need_by(c)
    new_order_by = compute_order_by_date(c.needed_on_site_date, c.lead_time_days)
    previous = c.order_by_date
    c.order_by_date = new_order_by
    if c.commitment_kind != "purchase_order":
        return False
    if c.status == "draft":
        return False
    if new_order_by is None:
        return False
    if previous == new_order_by and c.last_notified_order_by_date == new_order_by:
        return False
    if previous == new_order_by and c.supplier_confirm_status in (
        SUPPLIER_CONFIRM_SENT,
        SUPPLIER_CONFIRM_CONFIRMED,
    ):
        return False
    return previous != new_order_by or c.last_notified_order_by_date != new_order_by


def notify_supplier_order_by_change(c: Commitment) -> dict[str, Any]:
    """Email the PO vendor contact that the order-by date changed."""
    to = _vendor_contact_email(c)
    project = c.project or db.session.get(Project, c.project_id)
    project_name = (project.name if project else None) or "Project"
    po_ref = c.reference_number or "PO"
    order_by = c.order_by_date.isoformat() if c.order_by_date else "—"
    needed = c.needed_on_site_date.isoformat() if c.needed_on_site_date else "—"
    lead = str(c.lead_time_days) if c.lead_time_days is not None else "—"
    subject = f"[USIS] Order-by date update — {po_ref} / {project_name}"
    body = (
        f"Purchase order {po_ref} ({c.title or po_ref}) on {project_name} has a new order-by date.\n\n"
        f"Order by: {order_by}\n"
        f"Needed on site: {needed}\n"
        f"Lead time (days): {lead}\n\n"
        "Please confirm this date or reply with a revised promised ship date.\n"
    )
    result: dict[str, Any] = {"sent": False, "to": to, "dry_run": False, "error": None}
    if not to:
        result["error"] = "no vendor contact email"
        db.session.flush()
        return result
    mail = send_plain_notification_email(to=to, subject=subject, body=body)
    result.update(mail)
    if mail.get("sent") or mail.get("dry_run"):
        c.supplier_confirm_status = SUPPLIER_CONFIRM_SENT
        c.supplier_confirm_sent_at = _utcnow()
        c.supplier_confirm_at = None
        c.last_notified_order_by_date = c.order_by_date
        try:
            from . import _correspondence_service as corr

            corr.archive_outbound_message(
                project_id=c.project_id,
                subject=subject,
                body=body,
                from_email=_mail_from() or None,
                from_name="USIS",
                to_email=to,
            )
        except Exception:
            pass
    db.session.flush()
    return result


def maybe_auto_confirm_from_promised_ship(c: Commitment, previous_promised: date | None) -> None:
    if c.promised_ship_date is None:
        return
    if previous_promised == c.promised_ship_date:
        return
    if (c.supplier_confirm_status or "") != SUPPLIER_CONFIRM_SENT:
        return
    c.supplier_confirm_status = SUPPLIER_CONFIRM_CONFIRMED
    c.supplier_confirm_at = _utcnow()


def recalc_commitments_for_schedule_item(item: ProjectScheduleItem) -> list[Commitment]:
    """When a schedule start moves, every linked PO recalculates order-by."""
    rows = db.session.scalars(
        select(Commitment).where(
            Commitment.schedule_item_id == item.id,
            Commitment.commitment_kind == "purchase_order",
        )
    ).all()
    to_notify: list[Commitment] = []
    for c in rows:
        if sync_commitment_order_dates(c):
            to_notify.append(c)
    db.session.flush()
    return to_notify


def _po_row_public(c: Commitment, vendor_name: str, schedule: ProjectScheduleItem | None) -> dict[str, Any]:
    today = date.today()
    confirm = _effective_confirm_status(c, today=today)
    order_by = c.order_by_date
    return {
        "id": str(c.id),
        "commitment_id": str(c.id),
        "project_id": str(c.project_id),
        "po_number": c.reference_number,
        "title": c.title,
        "vendor_name": vendor_name,
        "status": c.status,
        "fulfillment_status": c.fulfillment_status,
        "lead_time_days": c.lead_time_days,
        "schedule_item_id": str(c.schedule_item_id) if c.schedule_item_id else None,
        "schedule_title": schedule.title if schedule else None,
        "needed_on_site_date": _iso(c.needed_on_site_date),
        "order_by_date": _iso(order_by),
        "promised_ship_date": _iso(c.promised_ship_date),
        "supplier_confirm_status": confirm,
        "supplier_confirm_sent_at": _iso(c.supplier_confirm_sent_at),
        "supplier_confirm_at": _iso(c.supplier_confirm_at),
        "late_vs_job": bool(c.late_vs_job),
        "buy_late": bool(order_by is not None and order_by < today),
        "order_by_this_week": bool(
            order_by is not None and today <= order_by <= today + timedelta(days=7)
        ),
    }


def serialize_order_fields(c: Commitment) -> dict[str, Any]:
    schedule = _load_schedule_item(c.project_id, c.schedule_item_id)
    vendor = c.vendor or db.session.get(Company, c.vendor_company_id)
    return _po_row_public(c, vendor.name if vendor else "", schedule)


def list_order_board(project_id: uuid.UUID, cu: CurrentUser, *, bucket: str = "all") -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    filt = (bucket or "all").strip().lower()
    if filt not in {"all", "late", "week", "overdue"}:
        raise ApiError("bucket must be all, late, week, or overdue", 400)
    stmt = (
        select(Commitment, Company.name, ProjectScheduleItem)
        .join(Company, Company.id == Commitment.vendor_company_id)
        .outerjoin(ProjectScheduleItem, ProjectScheduleItem.id == Commitment.schedule_item_id)
        .where(
            Commitment.project_id == project_id,
            Commitment.commitment_kind == "purchase_order",
        )
        .order_by(Commitment.order_by_date.nulls_last(), Commitment.reference_number)
    )
    items = []
    for c, vendor_name, schedule in db.session.execute(stmt):
        row = _po_row_public(c, vendor_name, schedule)
        if filt == "late" and not row["buy_late"]:
            continue
        if filt == "week" and not row["order_by_this_week"]:
            continue
        if filt == "overdue" and row["supplier_confirm_status"] != "overdue":
            continue
        items.append(row)
    return {"entity": "project_order_board", "items": items}


def confirm_supplier_notice(
    project_id: uuid.UUID,
    commitment_id: uuid.UUID,
    data: Mapping[str, Any],
    cu: CurrentUser,
) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = db.session.scalar(
        select(Commitment).where(Commitment.id == commitment_id, Commitment.project_id == project_id)
    )
    if c is None or c.commitment_kind != "purchase_order":
        raise ApiError("purchase order not found", 404)
    promised = data.get("promised_ship_date")
    if promised not in (None, ""):
        from ._commitment_service import _parse_date

        parsed = _parse_date(promised)
        if parsed is None:
            raise ApiError("invalid promised_ship_date", 400)
        c.promised_ship_date = parsed
    c.supplier_confirm_status = SUPPLIER_CONFIRM_CONFIRMED
    c.supplier_confirm_at = _utcnow()
    db.session.flush()
    db.session.commit()
    return {"entity": "supplier_confirm", "item": serialize_order_fields(c)}


def _qty_open(li: CommitmentLineItem) -> Decimal:
    return max(Decimal("0"), _dec(li.quantity) - _dec(li.qty_received))


def list_receivables(project_id: uuid.UUID, cu: CurrentUser, *, due: str = "open") -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    due_f = (due or "open").strip().lower()
    if due_f not in {"today", "week", "open"}:
        raise ApiError("due must be today, week, or open", 400)
    today = date.today()
    week_end = today + timedelta(days=7)
    stmt = (
        select(Commitment, Company.name)
        .join(Company, Company.id == Commitment.vendor_company_id)
        .options(selectinload(Commitment.line_items))
        .where(
            Commitment.project_id == project_id,
            Commitment.commitment_kind == "purchase_order",
        )
    )
    items = []
    for c, vendor_name in db.session.execute(stmt):
        qty_ordered = sum((_dec(li.quantity) for li in (c.line_items or [])), Decimal("0"))
        qty_received = sum((_dec(li.qty_received) for li in (c.line_items or [])), Decimal("0"))
        qty_open = max(Decimal("0"), qty_ordered - qty_received)
        has_open = qty_open > 0
        needed = c.needed_on_site_date
        if due_f == "open" and not has_open:
            continue
        if due_f == "today" and (not has_open or needed != today):
            continue
        if due_f == "week" and (not has_open or needed is None or needed < today or needed > week_end):
            continue
        items.append(
            {
                "commitment_id": str(c.id),
                "po_number": c.reference_number,
                "title": c.title,
                "vendor_name": vendor_name,
                "needed_on_site_date": _iso(needed),
                "promised_ship_date": _iso(c.promised_ship_date),
                "fulfillment_status": c.fulfillment_status,
                "qty_ordered": str(qty_ordered),
                "qty_received": str(qty_received),
                "qty_open": str(qty_open),
                "line_count": len(c.line_items or []),
                "has_open_qty": has_open,
            }
        )
    items.sort(key=lambda r: (r["needed_on_site_date"] or "9999", r["po_number"] or ""))
    return {"entity": "project_receivables", "items": items}


def _shipment_qty(s: PurchaseOrderShipment) -> Decimal:
    return sum((_dec(ln.quantity) for ln in (s.lines or [])), Decimal("0"))


def _shipment_public(s: PurchaseOrderShipment, c: Commitment, vendor_name: str) -> dict[str, Any]:
    status = s.shipment_status or "pending"
    shipped = status in SHIPPED_STATUSES
    expected = s.estimated_delivery_date or c.needed_on_site_date
    return {
        "shipment_id": str(s.id),
        "commitment_id": str(c.id),
        "po_number": c.reference_number,
        "title": c.title,
        "vendor_name": vendor_name,
        "expected_date": _iso(expected),
        "shipment_status": status,
        "shipped": shipped,
        "carrier": s.carrier if shipped else None,
        "tracking_number": s.tracking_number if shipped else None,
        "tracking_url": s.tracking_url if shipped else None,
        "promised_ship_date": _iso(s.promised_ship_date or c.promised_ship_date),
        "actual_ship_date": _iso(s.actual_ship_date),
        "estimated_delivery_date": _iso(s.estimated_delivery_date),
        "actual_delivery_date": _iso(s.actual_delivery_date),
        "last_note": s.last_note,
        "qty_on_shipment": str(_shipment_qty(s)),
    }


def list_deliveries(
    project_id: uuid.UUID,
    cu: CurrentUser,
    *,
    from_date: date | None = None,
    to_date: date | None = None,
) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    today = date.today()
    start = from_date or today
    end = to_date or (today + timedelta(days=14))
    stmt = (
        select(PurchaseOrderShipment, Commitment, Company.name)
        .join(Commitment, Commitment.id == PurchaseOrderShipment.commitment_id)
        .join(Company, Company.id == Commitment.vendor_company_id)
        .options(selectinload(PurchaseOrderShipment.lines))
        .where(
            Commitment.project_id == project_id,
            Commitment.commitment_kind == "purchase_order",
            PurchaseOrderShipment.shipment_status != "cancelled",
        )
    )
    items = []
    for s, c, vendor_name in db.session.execute(stmt):
        expected = s.estimated_delivery_date or c.needed_on_site_date
        in_motion = (s.shipment_status or "") in {"in_transit", "out_for_delivery"}
        in_window = expected is not None and start <= expected <= end
        if not in_window and not in_motion:
            continue
        items.append(_shipment_public(s, c, vendor_name))
    items.sort(key=lambda r: (r["expected_date"] or "9999", r["po_number"] or ""))
    return {"entity": "project_deliveries", "items": items}


def get_receive_detail(project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    c = db.session.scalar(
        select(Commitment)
        .options(
            selectinload(Commitment.line_items),
            selectinload(Commitment.shipments).selectinload(PurchaseOrderShipment.lines),
            selectinload(Commitment.receipts).selectinload(PurchaseOrderReceipt.lines),
            selectinload(Commitment.vendor),
        )
        .where(Commitment.id == commitment_id, Commitment.project_id == project_id)
    )
    if c is None or c.commitment_kind != "purchase_order":
        raise ApiError("purchase order not found", 404)
    vendor_name = c.vendor.name if c.vendor else ""
    from . import _purchase_order_fulfillment as po_ful

    return {
        "entity": "purchase_order_receive",
        "item": {
            "commitment_id": str(c.id),
            "project_id": str(c.project_id),
            "po_number": c.reference_number,
            "title": c.title,
            "vendor_name": vendor_name,
            "needed_on_site_date": _iso(c.needed_on_site_date),
            "fulfillment_status": c.fulfillment_status,
        },
        "lines": [
            {
                "id": str(li.id),
                "description": li.description,
                "quantity": str(li.quantity),
                "qty_received": str(li.qty_received),
                "qty_open": str(_qty_open(li)),
                "unit": li.unit,
            }
            for li in (c.line_items or [])
        ],
        "shipments": [_shipment_public(s, c, vendor_name) for s in (c.shipments or []) if s.shipment_status != "cancelled"],
        "receipts": [po_ful.serialize_receipt(r) for r in (c.receipts or [])],
    }


def create_field_receipt(
    project_id: uuid.UUID,
    commitment_id: uuid.UUID,
    data: Mapping[str, Any],
    cu: CurrentUser,
) -> tuple[dict[str, Any], int]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = db.session.scalar(
        select(Commitment)
        .options(selectinload(Commitment.line_items))
        .where(Commitment.id == commitment_id, Commitment.project_id == project_id)
    )
    if c is None or c.commitment_kind != "purchase_order":
        raise ApiError("purchase order not found", 404)
    client_id = _parse_uuid(data.get("client_id"))
    if data.get("client_id") and client_id is None:
        raise ApiError("invalid client_id", 400)
    if client_id is not None:
        existing = db.session.scalar(select(PurchaseOrderReceipt).where(PurchaseOrderReceipt.client_id == client_id))
        if existing is not None:
            return (
                {
                    "entity": "purchase_order_receipt",
                    "id": str(existing.id),
                    "commitment_id": str(existing.commitment_id),
                    "status": existing.status,
                    "held_unapproved": existing.status == "draft",
                    "fulfillment_status": c.fulfillment_status,
                    "created": False,
                },
                200,
            )
    condition = str(data.get("condition") or "").strip().lower()
    if condition not in FIELD_RECEIPT_CONDITIONS:
        raise ApiError("condition must be accepted, short, damaged, or held_unapproved", 400)
    photo_ids = data.get("photo_ids") if isinstance(data.get("photo_ids"), list) else []
    if condition == "damaged" and not photo_ids:
        raise ApiError("photos required for damaged", 400)
    raw_lines = data.get("lines") if isinstance(data.get("lines"), list) else []
    if not raw_lines:
        raise ApiError("lines required", 400)
    if condition != "held_unapproved":
        open_total = sum((_qty_open(li) for li in (c.line_items or [])), Decimal("0"))
        if open_total <= 0:
            raise ApiError("all qty already received", 409)
    from . import _commitment_service as commitment_svc

    body = commitment_svc.create_purchase_order_receipt(commitment_id, data, cu)
    body["created"] = True
    return body, 201


def _comm_item(
    *,
    source: str,
    kind_label: str,
    at: datetime | date | None,
    subject: str,
    preview: str = "",
    direction: str = "internal",
    from_name: str | None = None,
    from_email: str | None = None,
    to_email: str | None = None,
    item_id: str | None = None,
    download_url: str | None = None,
) -> dict[str, Any]:
    return {
        "id": item_id,
        "source": source,
        "kind_label": kind_label,
        "direction": direction,
        "at": _iso(at),
        "subject": subject,
        "preview": (preview or "")[:400],
        "from_name": from_name,
        "from_email": from_email,
        "to_email": to_email,
        "download_url": download_url,
    }


def _comm_blob(*parts: Any) -> str:
    return " ".join(str(p or "") for p in parts).lower()


def _matches_po_thread(blob: str, tokens: list[str]) -> bool:
    if not blob or not tokens:
        return False
    return any(t in blob for t in tokens)


def _mailbox_search_targets(cu: CurrentUser) -> list[str]:
    boxes: list[str] = []
    system = (_mail_from() or "").strip()
    if system:
        boxes.append(system)
    try:
        from . import _correspondence_service as corr

        boxes.extend(corr.configured_mailboxes())
    except Exception:
        pass
    user_email = ""
    if cu.user is not None:
        user_email = (getattr(cu.user, "email", None) or "").strip()
    if user_email and "@" in user_email:
        boxes.append(user_email)
    seen: set[str] = set()
    out: list[str] = []
    for b in boxes:
        key = b.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(b.strip())
    return out


def list_commitment_communications(
    project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser
) -> dict[str, Any]:
    """Emails and order/delivery notes between USIS and the PO vendor."""
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    c = db.session.scalar(
        select(Commitment)
        .options(
            selectinload(Commitment.shipments).selectinload(PurchaseOrderShipment.lines),
            selectinload(Commitment.receipts),
            selectinload(Commitment.vendor),
        )
        .where(Commitment.id == commitment_id, Commitment.project_id == project_id)
    )
    if c is None or c.commitment_kind != "purchase_order":
        raise ApiError("purchase order not found", 404)
    vendor = c.vendor or db.session.get(Company, c.vendor_company_id)
    vendor_name = vendor.name if vendor else ""
    vendor_email = _vendor_contact_email(c)
    po_ref = (c.reference_number or "").strip()
    tokens: list[str] = []
    if po_ref and len(po_ref) >= 3:
        tokens.append(po_ref.lower())
    if vendor_email:
        tokens.append(vendor_email.lower())
    if vendor_name and len(vendor_name) >= 4:
        tokens.append(vendor_name.lower())

    items: list[dict[str, Any]] = []
    if c.supplier_confirm_sent_at:
        items.append(
            _comm_item(
                source="order_notice",
                kind_label="Order-by notice",
                at=c.supplier_confirm_sent_at,
                subject=f"Order-by date update — {po_ref or 'PO'}",
                preview=(
                    f"Order by: {c.order_by_date.isoformat() if c.order_by_date else '—'}; "
                    f"needed on site: {c.needed_on_site_date.isoformat() if c.needed_on_site_date else '—'}"
                ),
                direction="outbound",
                from_name="USIS",
                from_email=_mail_from() or None,
                to_email=vendor_email,
            )
        )
    if c.supplier_confirm_at:
        items.append(
            _comm_item(
                source="supplier_confirm",
                kind_label="Vendor confirmation",
                at=c.supplier_confirm_at,
                subject=f"Supplier confirmed — {po_ref or 'PO'}",
                preview=(
                    f"Promised ship: {c.promised_ship_date.isoformat() if c.promised_ship_date else '—'}"
                ),
                direction="inbound",
                from_name=vendor_name or None,
                from_email=vendor_email,
            )
        )
    for s in c.shipments or []:
        if (s.shipment_status or "") == "cancelled":
            continue
        bits = [
            s.carrier,
            s.tracking_number,
            s.shipment_status,
            f"est. delivery {s.estimated_delivery_date.isoformat()}" if s.estimated_delivery_date else None,
            s.last_note,
        ]
        items.append(
            _comm_item(
                source="shipment",
                kind_label="Shipment / delivery",
                at=s.actual_ship_date or s.promised_ship_date or s.updated_at or s.created_at,
                subject=f"Shipment — {po_ref or 'PO'}",
                preview=" · ".join(str(b) for b in bits if b),
                direction="inbound" if s.tracking_number else "internal",
                from_name=vendor_name or None,
                item_id=str(s.id),
            )
        )
    for r in c.receipts or []:
        items.append(
            _comm_item(
                source="receipt",
                kind_label="Field receipt",
                at=r.received_on or r.created_at,
                subject=f"Received — {po_ref or 'PO'}",
                preview=" · ".join(
                    str(b)
                    for b in (r.condition, r.packing_slip_ref, r.notes, r.status)
                    if b
                ),
                direction="internal",
                item_id=str(r.id),
            )
        )
    mat_rows = db.session.scalars(
        select(ProjectMaterialOrder).where(ProjectMaterialOrder.commitment_id == c.id)
    ).all()
    for mo in mat_rows:
        bits = [
            mo.description,
            f"order {mo.order_date.isoformat()}" if mo.order_date else None,
            f"delivery {mo.expected_delivery_date.isoformat()}" if mo.expected_delivery_date else None,
            mo.shipping_company,
            mo.tracking_number,
            mo.notes,
        ]
        items.append(
            _comm_item(
                source="material_order",
                kind_label="Material order",
                at=mo.order_date or mo.expected_delivery_date or mo.created_at,
                subject=mo.description or f"Material order — {po_ref or 'PO'}",
                preview=" · ".join(str(b) for b in bits if b),
                direction="internal",
                from_name=mo.vendor_name or vendor_name or None,
                item_id=str(mo.id),
            )
        )

    seen_keys: set[str] = set()
    corr_rows = db.session.scalars(
        select(CorrespondenceItem)
        .where(CorrespondenceItem.project_id == project_id)
        .order_by(CorrespondenceItem.sent_at.desc().nullslast())
        .limit(500)
    ).all()
    for row in corr_rows:
        blob = _comm_blob(row.subject, row.from_email, row.from_name, row.search_text)
        if not tokens or not _matches_po_thread(blob, tokens):
            continue
        key = f"corr:{row.id}"
        seen_keys.add(key)
        items.append(
            _comm_item(
                source="correspondence",
                kind_label="Email",
                at=row.sent_at or row.created_at,
                subject=row.subject or "(no subject)",
                preview=(row.search_text or "")[:400],
                direction="outbound" if (row.source_type or "") == "outbound" else "inbound",
                from_name=row.from_name,
                from_email=row.from_email,
                item_id=str(row.id),
                download_url=f"/api/correspondence/{row.id}/download",
            )
        )

    mailbox: dict[str, Any] = {"searched": False, "error": None, "mailboxes": []}
    query = po_ref if po_ref and len(po_ref) >= 3 else (vendor_email or "")
    if query and _graph_configured():
        mailbox["searched"] = True
        try:
            from ._notifications import search_mailbox_messages
        except Exception as exc:
            mailbox["error"] = str(exc)
            search_mailbox_messages = None  # type: ignore[assignment]
        if search_mailbox_messages is not None:
            errors: list[str] = []
            for box in _mailbox_search_targets(cu):
                mailbox["mailboxes"].append(box)
                try:
                    listing = search_mailbox_messages(mailbox=box, query=query, top=25)
                except Exception as exc:
                    errors.append(f"{box}: {exc}")
                    continue
                for msg in listing.get("items") or []:
                    blob = _comm_blob(
                        msg.get("subject"),
                        (msg.get("from") or {}).get("address"),
                        (msg.get("from") or {}).get("name"),
                        msg.get("preview"),
                        " ".join((x.get("address") or "") for x in (msg.get("to") or [])),
                    )
                    if not tokens or not _matches_po_thread(blob, tokens):
                        continue
                    mid = str(msg.get("id") or "")
                    key = f"mail:{mid}"
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    frm = msg.get("from") if isinstance(msg.get("from"), dict) else {}
                    to_list = msg.get("to") if isinstance(msg.get("to"), list) else []
                    to_addr = (to_list[0].get("address") if to_list and isinstance(to_list[0], dict) else None)
                    items.append(
                        _comm_item(
                            source="mailbox",
                            kind_label="Mailbox",
                            at=_parse_mailbox_dt(msg.get("received")),
                            subject=str(msg.get("subject") or "(no subject)"),
                            preview=str(msg.get("preview") or ""),
                            direction="inbound",
                            from_name=(frm or {}).get("name"),
                            from_email=(frm or {}).get("address"),
                            to_email=to_addr,
                            item_id=mid,
                        )
                    )
            if errors:
                mailbox["error"] = "; ".join(errors[:5])

    if any(
        i.get("source") == "correspondence"
        and "order-by date update" in (i.get("subject") or "").lower()
        for i in items
    ):
        items = [i for i in items if i.get("source") != "order_notice"]

    items.sort(key=lambda r: r.get("at") or "", reverse=True)
    return {
        "entity": "purchase_order_communications",
        "item": {
            "commitment_id": str(c.id),
            "project_id": str(c.project_id),
            "po_number": po_ref or None,
            "title": c.title,
            "vendor_name": vendor_name,
            "vendor_email": vendor_email,
        },
        "items": items,
        "mailbox": mailbox,
    }


def _parse_mailbox_dt(raw: Any) -> datetime | None:
    if not raw:
        return None
    s = str(raw).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt
