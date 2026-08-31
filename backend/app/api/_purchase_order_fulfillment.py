"""Material PO shipments, qty rollups, fulfillment status, and 3-way match."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import (
    AuditLog,
    Commitment,
    CommitmentLineItem,
    PurchaseOrderReceipt,
    PurchaseOrderReceiptLine,
    PurchaseOrderShipment,
    PurchaseOrderShipmentLine,
    VendorInvoice,
)
from ..models.purchase_order import SHIPMENT_STATUSES
from . import _workflow_service as wf
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat()


def _dec(v: Any) -> Decimal:
    if v is None or v == "":
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0")


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, date) and not isinstance(raw, datetime):
        return raw
    if isinstance(raw, datetime):
        return raw.date()
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def _load_po(commitment_id: uuid.UUID) -> Commitment:
    c = db.session.scalars(
        select(Commitment)
        .where(Commitment.id == commitment_id)
        .options(
            selectinload(Commitment.line_items),
            selectinload(Commitment.shipments).selectinload(PurchaseOrderShipment.lines),
            selectinload(Commitment.receipts).selectinload(PurchaseOrderReceipt.lines),
        )
    ).first()
    if c is None:
        raise ApiError("purchase order not found", 404)
    if c.commitment_kind != "purchase_order":
        raise ApiError("not a purchase order", 400)
    return c


def _audit(*, cu: CurrentUser | None, entity_id: uuid.UUID, action: str, message: str, changes: dict | None = None) -> None:
    db.session.add(
        AuditLog(
            entity_type="purchase_order",
            entity_id=entity_id,
            action=action,
            message=message,
            changes=changes or {},
            user_id=cu.id if cu else None,
        )
    )


def serialize_shipment(s: PurchaseOrderShipment) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "commitmentId": str(s.commitment_id),
        "sortOrder": s.sort_order,
        "carrier": s.carrier,
        "trackingNumber": s.tracking_number,
        "trackingUrl": s.tracking_url,
        "shipmentStatus": s.shipment_status,
        "promisedShipDate": _iso(s.promised_ship_date),
        "actualShipDate": _iso(s.actual_ship_date),
        "estimatedDeliveryDate": _iso(s.estimated_delivery_date),
        "actualDeliveryDate": _iso(s.actual_delivery_date),
        "lastNote": s.last_note,
        "lines": [
            {
                "id": str(ln.id),
                "commitmentLineItemId": str(ln.commitment_line_item_id),
                "sortOrder": ln.sort_order,
                "quantity": str(ln.quantity),
                "notes": ln.notes,
            }
            for ln in (s.lines or [])
        ],
    }


def serialize_receipt(r: PurchaseOrderReceipt) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "commitmentId": str(r.commitment_id),
        "shipmentId": str(r.shipment_id) if r.shipment_id else None,
        "receivedOn": _iso(r.received_on),
        "packingSlipRef": r.packing_slip_ref,
        "status": r.status,
        "notes": r.notes,
        "clientId": str(r.client_id) if r.client_id else None,
        "condition": r.condition,
        "photoIds": list(r.photo_ids or []),
        "lines": [
            {
                "id": str(ln.id),
                "commitmentLineItemId": str(ln.commitment_line_item_id),
                "sortOrder": ln.sort_order,
                "quantity": str(ln.quantity),
                "notes": ln.notes,
            }
            for ln in (r.lines or [])
        ],
    }


def refresh_line_qty_rollups(c: Commitment) -> None:
    shipped: dict[uuid.UUID, Decimal] = {}
    received: dict[uuid.UUID, Decimal] = {}
    shipments = db.session.scalars(
        select(PurchaseOrderShipment)
        .where(PurchaseOrderShipment.commitment_id == c.id)
        .options(selectinload(PurchaseOrderShipment.lines))
    ).all()
    receipts = db.session.scalars(
        select(PurchaseOrderReceipt)
        .where(PurchaseOrderReceipt.commitment_id == c.id)
        .options(selectinload(PurchaseOrderReceipt.lines))
    ).all()
    for sh in shipments:
        if sh.shipment_status == "cancelled":
            continue
        for ln in sh.lines or []:
            shipped[ln.commitment_line_item_id] = shipped.get(ln.commitment_line_item_id, Decimal("0")) + (
                ln.quantity or Decimal("0")
            )
    for rc in receipts:
        if rc.status == "void":
            continue
        for ln in rc.lines or []:
            received[ln.commitment_line_item_id] = received.get(ln.commitment_line_item_id, Decimal("0")) + (
                ln.quantity or Decimal("0")
            )
    invoiced_qty: dict[uuid.UUID, Decimal] = {}
    invoices = db.session.scalars(
        select(VendorInvoice).where(VendorInvoice.commitment_id == c.id)
    ).all()
    if invoices:
        for li in c.line_items or []:
            invoiced_qty[li.id] = li.quantity or Decimal("0")
    for li in c.line_items or []:
        li.qty_shipped = shipped.get(li.id, Decimal("0"))
        li.qty_received = received.get(li.id, Decimal("0"))
        li.qty_invoiced = invoiced_qty.get(li.id, Decimal("0"))


def refresh_fulfillment_status(c: Commitment) -> str:
    refresh_line_qty_rollups(c)
    lines = [li for li in (c.line_items or []) if (li.quantity or Decimal("0")) > 0]
    if not lines:
        active = [s for s in (c.shipments or []) if s.shipment_status not in ("cancelled",)]
        c.fulfillment_status = "in_transit" if any(s.shipment_status in ("in_transit", "out_for_delivery") for s in active) else "open"
        return c.fulfillment_status
    all_received = all((li.qty_received or 0) >= (li.quantity or 0) for li in lines)
    any_received = any((li.qty_received or 0) > 0 for li in lines)
    all_shipped = all((li.qty_shipped or 0) >= (li.quantity or 0) for li in lines)
    any_shipped = any((li.qty_shipped or 0) > 0 for li in lines)
    shipments = db.session.scalars(select(PurchaseOrderShipment).where(PurchaseOrderShipment.commitment_id == c.id)).all()
    any_in_transit = any(
        s.shipment_status in ("in_transit", "out_for_delivery")
        for s in shipments
        if s.shipment_status != "cancelled"
    )
    if all_received:
        status = "received"
    elif any_received:
        status = "partially_received"
    elif all_shipped:
        status = "shipped"
    elif any_in_transit:
        status = "in_transit"
    elif any_shipped:
        status = "partially_shipped"
    else:
        status = "open"
    c.fulfillment_status = status
    actuals = [s.actual_ship_date for s in shipments if s.actual_ship_date]
    if actuals and c.actual_ship_date is None:
        c.actual_ship_date = min(actuals)
    return status


def compute_three_way_match(c: Commitment) -> dict[str, Any]:
    refresh_fulfillment_status(c)
    invoices = db.session.scalars(select(VendorInvoice).where(VendorInvoice.commitment_id == c.id)).all()
    po_amount = c.total_amount
    if po_amount is None:
        po_amount = sum((li.line_total or Decimal("0")) for li in (c.line_items or []))
    inv_amount = sum((inv.amount or Decimal("0")) for inv in invoices)
    lines = list(c.line_items or [])
    qty_ok = bool(lines) and all((li.qty_received or 0) >= (li.quantity or 0) for li in lines if (li.quantity or 0) > 0)
    amount_ok = bool(invoices) and po_amount is not None and abs(Decimal(str(po_amount)) - inv_amount) <= Decimal("0.05")
    if not invoices:
        status = "unmatched"
    elif qty_ok and amount_ok:
        status = "matched"
    elif qty_ok:
        status = "quantity_ok"
    elif amount_ok:
        status = "amount_ok"
    else:
        status = "exception"
    notes = f"PO {po_amount} vs invoices {inv_amount}; qty_ok={qty_ok}"
    now = _utcnow()
    for inv in invoices:
        inv.match_status = status
        inv.match_notes = notes
        inv.match_checked_at = now
    return {
        "matchStatus": status,
        "quantityOk": qty_ok,
        "amountOk": amount_ok,
        "poAmount": str(po_amount) if po_amount is not None else None,
        "invoiceAmount": str(inv_amount),
        "invoiceCount": len(invoices),
        "fulfillmentStatus": c.fulfillment_status,
    }


def _advance(c: Commitment, step_key: str, cu: CurrentUser | None) -> None:
    wf.complete_subject_step(
        process_key=wf.PROCESS_PURCHASE_ORDER,
        subject_type="commitment",
        subject_id=c.id,
        step_key=step_key,
        cu=cu,
    )


def list_shipments(commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    from ._commitment_service import _can_view

    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    c = _load_po(commitment_id)
    return {"entity": "purchase_order_shipments", "items": [serialize_shipment(s) for s in (c.shipments or [])]}


def create_shipment(commitment_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    from ._commitment_service import _can_mutate

    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_po(commitment_id)
    status = str(data.get("shipment_status") or data.get("shipmentStatus") or "pending").strip()
    if status not in SHIPMENT_STATUSES:
        raise ApiError("invalid shipment_status", 400)
    shipment = PurchaseOrderShipment(
        commitment_id=c.id,
        sort_order=int(data.get("sort_order") or data.get("sortOrder") or len(c.shipments or [])),
        carrier=(str(data.get("carrier") or "").strip()[:40] or None),
        tracking_number=(str(data.get("tracking_number") or data.get("trackingNumber") or "").strip()[:120] or None),
        tracking_url=(str(data.get("tracking_url") or data.get("trackingUrl") or "").strip()[:1024] or None),
        shipment_status=status,
        promised_ship_date=_parse_date(data.get("promised_ship_date") or data.get("promisedShipDate")),
        actual_ship_date=_parse_date(data.get("actual_ship_date") or data.get("actualShipDate")),
        estimated_delivery_date=_parse_date(data.get("estimated_delivery_date") or data.get("estimatedDeliveryDate")),
        actual_delivery_date=_parse_date(data.get("actual_delivery_date") or data.get("actualDeliveryDate")),
        last_note=(str(data.get("last_note") or data.get("lastNote") or "").strip() or None),
        created_by_user_id=cu.id,
    )
    db.session.add(shipment)
    db.session.flush()
    raw_lines = data.get("lines") if isinstance(data.get("lines"), list) else []
    line_ids = {li.id for li in (c.line_items or [])}
    for idx, raw in enumerate(raw_lines):
        if not isinstance(raw, Mapping):
            continue
        lid = _parse_uuid(raw.get("commitment_line_item_id") or raw.get("line_id") or raw.get("commitmentLineItemId"))
        if lid is None or lid not in line_ids:
            raise ApiError("invalid commitment_line_item_id on shipment line", 400)
        db.session.add(
            PurchaseOrderShipmentLine(
                shipment_id=shipment.id,
                commitment_line_item_id=lid,
                sort_order=int(raw.get("sort_order") or idx),
                quantity=_dec(raw.get("quantity")),
                notes=(str(raw.get("notes") or "").strip() or None),
            )
        )
    if shipment.promised_ship_date and c.promised_ship_date is None:
        c.promised_ship_date = shipment.promised_ship_date
    db.session.flush()
    refresh_fulfillment_status(c)
    if shipment.promised_ship_date or shipment.actual_ship_date:
        _advance(c, "ship_schedule", cu)
    if shipment.tracking_number or shipment.tracking_url:
        _advance(c, "tracking", cu)
    _audit(cu=cu, entity_id=c.id, action="shipment_create", message="Added PO shipment")
    db.session.commit()
    return {"entity": "purchase_order_shipment", "item": serialize_shipment(shipment), "fulfillmentStatus": c.fulfillment_status}


def patch_shipment(
    commitment_id: uuid.UUID, shipment_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser
) -> dict[str, Any]:
    from ._commitment_service import _can_mutate

    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_po(commitment_id)
    shipment = next((s for s in (c.shipments or []) if s.id == shipment_id), None)
    if shipment is None:
        raise ApiError("shipment not found", 404)
    if "shipment_status" in data or "shipmentStatus" in data:
        status = str(data.get("shipment_status") or data.get("shipmentStatus") or "").strip()
        if status not in SHIPMENT_STATUSES:
            raise ApiError("invalid shipment_status", 400)
        shipment.shipment_status = status
    for src, attr in (
        ("carrier", "carrier"),
        ("tracking_number", "tracking_number"),
        ("trackingNumber", "tracking_number"),
        ("tracking_url", "tracking_url"),
        ("trackingUrl", "tracking_url"),
        ("last_note", "last_note"),
        ("lastNote", "last_note"),
    ):
        if src in data:
            val = data.get(src)
            setattr(shipment, attr, (str(val).strip() or None) if val is not None else None)
    for src, attr in (
        ("promised_ship_date", "promised_ship_date"),
        ("promisedShipDate", "promised_ship_date"),
        ("actual_ship_date", "actual_ship_date"),
        ("actualShipDate", "actual_ship_date"),
        ("estimated_delivery_date", "estimated_delivery_date"),
        ("estimatedDeliveryDate", "estimated_delivery_date"),
        ("actual_delivery_date", "actual_delivery_date"),
        ("actualDeliveryDate", "actual_delivery_date"),
    ):
        if src in data:
            setattr(shipment, attr, _parse_date(data.get(src)))
    db.session.flush()
    refresh_fulfillment_status(c)
    if shipment.tracking_number or shipment.tracking_url:
        _advance(c, "tracking", cu)
    if shipment.promised_ship_date or shipment.actual_ship_date:
        _advance(c, "ship_schedule", cu)
    _audit(cu=cu, entity_id=c.id, action="shipment_patch", message="Updated PO shipment")
    db.session.commit()
    return {"entity": "purchase_order_shipment", "item": serialize_shipment(shipment), "fulfillmentStatus": c.fulfillment_status}


def delete_shipment(commitment_id: uuid.UUID, shipment_id: uuid.UUID, cu: CurrentUser) -> None:
    from ._commitment_service import _can_mutate

    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_po(commitment_id)
    shipment = next((s for s in (c.shipments or []) if s.id == shipment_id), None)
    if shipment is None:
        raise ApiError("shipment not found", 404)
    db.session.delete(shipment)
    db.session.flush()
    refresh_fulfillment_status(c)
    _audit(cu=cu, entity_id=c.id, action="shipment_delete", message="Deleted PO shipment")
    db.session.commit()


def post_receipt(commitment_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    """Create a receipt, roll up qty, honor submittal holds, advance workflow."""
    from . import _commitment_service as commitment_svc

    return commitment_svc.create_purchase_order_receipt(commitment_id, data, cu)


def run_three_way_match(commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    from ._commitment_service import _can_mutate

    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    c = _load_po(commitment_id)
    result = compute_three_way_match(c)
    if result["matchStatus"] in ("matched", "quantity_ok", "amount_ok"):
        _advance(c, "three_way_match", cu)
    _audit(cu=cu, entity_id=c.id, action="three_way_match", message=f"Match {result['matchStatus']}")
    db.session.commit()
    return {"entity": "purchase_order_match", **result}


def tracking_payload(commitment_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    from ._commitment_service import _can_view, get_commitment_detail

    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    c = _load_po(commitment_id)
    refresh_fulfillment_status(c)
    match = compute_three_way_match(c)
    inst = wf.instance_for_subject(wf.PROCESS_PURCHASE_ORDER, "commitment", c.id)
    detail = get_commitment_detail(c.project_id, c.id, cu)
    db.session.flush()
    return {
        "entity": "purchase_order_tracking",
        "item": detail["item"],
        "lineItems": detail["line_items"],
        "shipments": [serialize_shipment(s) for s in (c.shipments or [])],
        "receipts": [serialize_receipt(r) for r in (c.receipts or [])],
        "match": match,
        "workflow": wf.instance_public(inst) if inst else None,
    }
