"""Create a draft purchase order from an awarded RFP vendor quote."""
from __future__ import annotations

import re
import uuid
from decimal import Decimal
from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models import (
    Commitment,
    CostCode,
    EstimateLineItem,
    LeadEstimate,
    Rfp,
    RfpLineItem,
    RfpVendorQuote,
)
from ._commitment_service import create_commitment
from ._perms import CurrentUser
from ._rfi_service import ApiError

_CSI_KEEP = re.compile(r"[^A-Za-z0-9]")


def commitment_summary(c: Commitment | None) -> dict[str, Any] | None:
    if c is None:
        return None
    return {
        "id": str(c.id),
        "project_id": str(c.project_id),
        "reference_number": c.reference_number,
        "status": c.status,
    }


def po_for_rfp(rfp: Rfp) -> Commitment | None:
    return db.session.scalar(
        select(Commitment)
        .where(Commitment.rfp_id == rfp.id, Commitment.commitment_kind == "purchase_order")
        .order_by(Commitment.created_at.desc())
    )


def resolve_award_project_id(rfp: Rfp) -> uuid.UUID:
    if rfp.project_id:
        return rfp.project_id
    if rfp.lead_estimate_id:
        le = db.session.get(LeadEstimate, rfp.lead_estimate_id)
        if le is not None and le.project_id:
            return le.project_id
    raise ApiError("Award the job to a project before creating a purchase order.", 400)


def next_po_number(project_id: uuid.UUID) -> str:
    existing = list(
        db.session.scalars(
            select(Commitment.reference_number).where(
                Commitment.project_id == project_id,
                Commitment.commitment_kind == "purchase_order",
            )
        ).all()
    )
    used = {str(r).strip().upper() for r in existing if r}
    n = len(used) + 1
    while True:
        candidate = f"PO-{n:03d}"
        if candidate.upper() not in used:
            return candidate
        n += 1


def _norm_csi(raw: str | None) -> str:
    return _CSI_KEEP.sub("", raw or "").upper()


def _match_cost_code_id(project_id: uuid.UUID, csi: str | None) -> str | None:
    needle = _norm_csi(csi)
    if not needle:
        return None
    codes = list(db.session.scalars(select(CostCode).where(CostCode.project_id == project_id)).all())
    for cc in codes:
        code_n = _norm_csi(cc.code)
        if code_n == needle or (code_n and needle.startswith(code_n)) or (needle and code_n.startswith(needle)):
            return str(cc.id)
    return None


def _as_decimal(raw: Any) -> Decimal | None:
    from ._rfp_body_service import _as_decimal as parse

    return parse(raw)


def quote_unit_prices(quote: RfpVendorQuote) -> dict[str, Decimal]:
    price_by_line: dict[str, Decimal] = {}
    lp = quote.line_prices
    if isinstance(lp, dict):
        for k, v in lp.items():
            if k in ("lines",):
                continue
            unit = None
            if isinstance(v, Mapping):
                if v.get("unit_price") is not None:
                    unit = _as_decimal(v.get("unit_price"))
                elif v.get("extension") is not None:
                    unit = _as_decimal(v.get("extension"))
            elif v is not None:
                unit = _as_decimal(v)
            if unit is not None:
                price_by_line[str(k)] = unit
        nested = lp.get("lines")
        if isinstance(nested, dict):
            for k, v in nested.items():
                if str(k) in price_by_line:
                    continue
                unit = _as_decimal(v.get("unit_price") if isinstance(v, Mapping) else v)
                if unit is not None:
                    price_by_line[str(k)] = unit
    elif isinstance(lp, list):
        for item in lp:
            if not isinstance(item, Mapping):
                continue
            lid = str(item.get("line_id") or "")
            if not lid:
                continue
            if item.get("unit_price") is not None:
                unit = _as_decimal(item.get("unit_price"))
            else:
                unit = _as_decimal(item.get("extension"))
            if unit is not None:
                price_by_line[lid] = unit
    return price_by_line


def _line_unit_cost(
    quote: RfpVendorQuote, line: RfpLineItem, price_by_line: dict[str, Decimal]
) -> Decimal:
    unit = price_by_line.get(str(line.id))
    if unit is not None:
        lp = quote.line_prices
        cell: Any = None
        if isinstance(lp, dict):
            cell = lp.get(str(line.id))
            if cell is None and isinstance(lp.get("lines"), dict):
                cell = lp["lines"].get(str(line.id))
        elif isinstance(lp, list):
            cell = next((x for x in lp if isinstance(x, Mapping) and str(x.get("line_id")) == str(line.id)), None)
        if isinstance(cell, Mapping) and cell.get("unit_price") is None and cell.get("extension") is not None:
            ext = _as_decimal(cell.get("extension"))
            qty = line.quantity if line.quantity not in (None, Decimal("0")) else None
            if ext is not None and qty:
                return (ext / qty).quantize(Decimal("0.0001"))
            if ext is not None:
                return ext
        return unit
    return Decimal("0")


def _estimate_line_id(rfp: Rfp, takeoff_line_id: uuid.UUID | None) -> str | None:
    if takeoff_line_id is None:
        return None
    q = select(EstimateLineItem.id).where(EstimateLineItem.takeoff_line_item_id == takeoff_line_id)
    if rfp.source_estimate_id:
        q = q.where(EstimateLineItem.estimate_id == rfp.source_estimate_id)
    found = db.session.scalar(q)
    return str(found) if found else None


def _po_notes(quote: RfpVendorQuote) -> str | None:
    bits: list[str] = []
    if quote.notes and str(quote.notes).strip():
        bits.append(str(quote.notes).strip())
    if quote.vendor_exclusions and str(quote.vendor_exclusions).strip():
        bits.append("Vendor exclusions: " + str(quote.vendor_exclusions).strip())
    return "\n".join(bits) if bits else None


def build_po_line_items(rfp: Rfp, quote: RfpVendorQuote, project_id: uuid.UUID) -> list[dict[str, Any]]:
    from ._rfp_body_service import visible_line_items

    visible = visible_line_items(rfp)
    prices = quote_unit_prices(quote)
    out: list[dict[str, Any]] = []
    if not visible:
        amount = quote.lump_sum_amount if quote.lump_sum_amount is not None else Decimal("0")
        out.append(
            {
                "item_number": "1",
                "description": f"Lump sum — {rfp.title or 'RFP'}",
                "quantity": "1",
                "unit": "LS",
                "unit_cost": str(amount),
                "resource": "material",
            }
        )
        return out
    for idx, ln in enumerate(visible):
        qty = ln.quantity
        unit = (ln.unit or "EA").strip() or "EA"
        if qty is None:
            qty = Decimal("1") if unit.upper() == "LS" else Decimal("0")
        unit_cost = _line_unit_cost(quote, ln, prices)
        if (
            quote.lump_sum_amount is not None
            and str(ln.id) not in prices
            and len(visible) == 1
        ):
            unit_cost = quote.lump_sum_amount
            if unit.upper() == "LS" and qty == Decimal("0"):
                qty = Decimal("1")
        row: dict[str, Any] = {
            "item_number": str(idx + 1),
            "description": (ln.description or "").strip() or (rfp.title or "RFP line"),
            "quantity": str(qty),
            "unit": unit,
            "unit_cost": str(unit_cost),
            "resource": "material",
            "rfp_line_item_id": str(ln.id),
        }
        if ln.source_takeoff_line_id:
            row["takeoff_line_item_id"] = str(ln.source_takeoff_line_id)
            eli = _estimate_line_id(rfp, ln.source_takeoff_line_id)
            if eli:
                row["estimate_line_item_id"] = eli
        cc = _match_cost_code_id(project_id, ln.csi_division)
        if cc:
            row["cost_code_id"] = cc
        out.append(row)
    return out


def create_draft_po_from_quote(
    rfp: Rfp, quote: RfpVendorQuote, cu: CurrentUser
) -> dict[str, Any]:
    if not quote.vendor_company_id:
        raise ApiError("Link this quote to a vendor company before awarding.", 400)
    project_id = resolve_award_project_id(rfp)
    existing = po_for_rfp(rfp)
    if existing is not None:
        awarded = rfp.awarded_quote_id
        if awarded is not None and awarded != quote.id:
            raise ApiError("this RFP already has a purchase order from a different awarded quote", 400)
        return commitment_summary(existing) or {}
    payload: dict[str, Any] = {
        "commitment_kind": "purchase_order",
        "vendor_company_id": str(quote.vendor_company_id),
        "title": (rfp.title or "").strip() or "Purchase order",
        "reference_number": next_po_number(project_id),
        "status": "draft",
        "rfp_id": str(rfp.id),
        "default_resource": "material",
        "line_items": build_po_line_items(rfp, quote, project_id),
    }
    if quote.vendor_contact_id:
        payload["vendor_contact_id"] = str(quote.vendor_contact_id)
    notes = _po_notes(quote)
    if notes:
        payload["notes"] = notes
    if cu.id:
        payload["issued_by_user_id"] = str(cu.id)
    created = create_commitment(project_id, payload, cu, commit=False)
    item = created.get("item") or {}
    return {
        "id": item.get("id"),
        "project_id": item.get("project_id") or str(project_id),
        "reference_number": item.get("reference_number"),
        "status": item.get("status") or "draft",
    }
