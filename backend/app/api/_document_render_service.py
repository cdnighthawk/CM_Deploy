"""Jinja2 HTML rendering for print-style documents (PO, client proposal).

Templates live under ``app/templates/documents/``. Routes return ``text/html``
for browser print / future PDF (e.g. WeasyPrint) pipelines.
"""
from __future__ import annotations

import os
import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping

from flask import current_app, render_template
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from ..extensions import db
from ..models import Company, Project
from ..models.door_opening import DoorOpening
from ..models.lead_estimate import LeadEstimate
from ..models.takeoff_line_item import TakeoffLineItem
from . import _commitment_service as commitment_svc
from ..services import door_schedule as door_schedule_svc
from ._perms import CurrentUser
from ._quote_report_columns import resolve_visible_columns
from ._rfi_service import ApiError


def _client_company_name(client: Any) -> str | None:
    if not isinstance(client, Mapping):
        return None
    comp = client.get("company")
    if isinstance(comp, Mapping):
        n = comp.get("name")
        return str(n).strip() if n else None
    return None


def _client_contact_line(client: Any) -> str | None:
    if not isinstance(client, Mapping):
        return None
    for key in ("primaryContact", "contact", "person", "primary_contact"):
        pc = client.get(key)
        if not isinstance(pc, Mapping):
            continue
        fn_raw = pc.get("firstName") or pc.get("first_name")
        ln_raw = pc.get("lastName") or pc.get("last_name")
        fn = str(fn_raw).strip() if fn_raw is not None else ""
        ln = str(ln_raw).strip() if ln_raw is not None else ""
        name = (fn + " " + ln).strip()
        email = pc.get("email") or pc.get("emailAddress")
        email_s = str(email).strip() if email else ""
        if name and email_s:
            return f"{name} · {email_s}"
        if name:
            return name
        if email_s:
            return email_s
    return None


def _can_view_procurement(cu: CurrentUser) -> bool:
    return (
        cu.is_dev_admin
        or cu.has_role("admin", "superuser", "standard")
        or cu.has_role("read_only", "readonly")
    )


def _seller_name() -> str:
    raw = (current_app.config.get("DOCUMENT_PRINT_COMPANY_NAME") or os.environ.get("DOCUMENT_PRINT_COMPANY_NAME") or "").strip()
    return raw or "USIS Construction Management"


def _print_logo_url() -> str | None:
    raw = (current_app.config.get("DOCUMENT_PRINT_LOGO_URL") or os.environ.get("DOCUMENT_PRINT_LOGO_URL") or "").strip()
    return raw or None


def _project_address_lines(p: Project) -> str | None:
    parts = [p.address_line1, p.address_line2, p.city, p.state, p.postal_code]
    bits = [x.strip() for x in parts if x and str(x).strip()]
    return ", ".join(bits) if bits else None


def _project_public_dict(p: Project) -> dict[str, Any]:
    return {
        "id": str(p.id),
        "name": p.name,
        "number": p.number,
        "project_type": p.project_type or "",
        "contract_value": str(p.contract_value) if p.contract_value is not None else None,
        "description": (p.description or "").strip() or None,
    }


def render_purchase_order_html(project_id: uuid.UUID, commitment_id: uuid.UUID, cu: CurrentUser) -> str:
    detail = commitment_svc.get_commitment_detail(project_id, commitment_id, cu)
    item = detail["item"]
    if item.get("commitment_kind") != "purchase_order":
        raise ApiError("This template is for purchase_order commitments only.", 400)

    p = db.session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError("project not found", 404)

    ctx = {
        "seller_name": _seller_name(),
        "print_logo_url": _print_logo_url(),
        "doc_title": "Purchase Order",
        "commitment": item,
        "line_items": detail.get("line_items") or [],
        "project": _project_public_dict(p),
        "project_address": _project_address_lines(p),
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return render_template("documents/purchase_order.html", **ctx)


def render_client_proposal_html(
    project_id: uuid.UUID,
    cu: CurrentUser,
    *,
    scope_commitment_id: uuid.UUID | None = None,
) -> str:
    """Proposal shell: project metadata + optional line items from a commitment (e.g. draft bid)."""
    if not _can_view_procurement(cu):
        raise ApiError("forbidden", 403)

    p = db.session.get(Project, project_id)
    if p is None or p.deleted_at is not None:
        raise ApiError("project not found", 404)

    owner = db.session.get(Company, p.owner_company_id) if p.owner_company_id else None
    client_name = owner.name if owner else "Client"

    scope_text = (p.description or "").strip() or "Scope of work to be finalized with the client."

    optional_lines: list[Mapping[str, Any]] = []
    if scope_commitment_id is not None:
        cd = commitment_svc.get_commitment_detail(project_id, scope_commitment_id, cu)
        optional_lines = list(cd.get("line_items") or [])

    ctx = {
        "seller_name": _seller_name(),
        "print_logo_url": _print_logo_url(),
        "client_name": client_name,
        "project": _project_public_dict(p),
        "project_address": _project_address_lines(p),
        "scope_text": scope_text,
        "optional_lines": optional_lines,
        "generated_at": date.today().isoformat(),
    }
    return render_template("documents/client_proposal.html", **ctx)


def _takeoff_line_row(t: TakeoffLineItem) -> dict[str, Any]:
    return {
        "section": t.section,
        "description": (t.description or "").strip(),
        "quantity": float(t.quantity),
        "unit": t.unit or "EA",
        "unit_cost": float(t.unit_cost),
        "extended_total": float(t.extended_total),
        "cost_type": t.cost_type or "M",
        "line_role": t.line_role,
        "job_cost_code": t.job_cost_code,
    }


def _takeoff_line_quote_row(t: TakeoffLineItem) -> dict[str, Any]:
    base = _takeoff_line_row(t)
    base["job_cost_code_description"] = (t.job_cost_code_description or "").strip() or None
    notes_raw = (t.notes or "").strip()
    base["notes"] = notes_raw or None
    mp = t.material_price
    if mp is not None:
        man = (mp.manufacturer or "").strip()
        item = (mp.item or "").strip()
        bits = [x for x in (man, item) if x]
        base["material_catalog"] = " · ".join(bits) if bits else None
    else:
        base["material_catalog"] = None
    return base


def _self_company_letterhead() -> dict[str, Any] | None:
    cid = db.session.scalar(
        select(Company.id)
        .where(Company.company_type == "self", Company.deleted_at.is_(None))
        .order_by(Company.created_at.asc())
        .limit(1)
    )
    if cid is None:
        return None
    c = db.session.get(Company, cid)
    if c is None:
        return None
    line12 = [x.strip() for x in (c.address_line1, c.address_line2) if x and str(x).strip()]
    address_block = ", ".join(line12) if line12 else None
    city_bits = [x.strip() for x in (c.city, c.state, c.postal_code) if x and str(x).strip()]
    city_line = ", ".join(city_bits) if city_bits else None
    return {
        "name": c.name,
        "address_block": address_block,
        "city_state_zip": city_line,
        "phone": (c.phone or "").strip() or None,
        "email": (c.email or "").strip() or None,
        "website": (c.website or "").strip() or None,
    }


def _lead_report_header(lead: LeadEstimate) -> dict[str, Any]:
    return {
        "id": str(lead.id),
        "external_id": lead.external_id,
        "name": lead.name,
        "number": lead.number,
        "trade_name": lead.trade_name or "",
    }


def _door_opening_report_dict(opening: DoorOpening) -> dict[str, Any]:
    base = door_schedule_svc.door_opening_public(opening, include_lines=False)
    lines = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.door_opening_id == opening.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
    ).all()
    base["takeoff_lines"] = [_takeoff_line_row(x) for x in lines]
    base["takeoff_line_count"] = len(lines)
    return base


def render_estimate_summary_html(
    lead: LeadEstimate,
    cu: CurrentUser,
    *,
    line_limit: int = 500,
) -> str:
    """Takeoff lines rollup for a lead (print)."""
    _ = cu
    lines_all = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.lead_estimate_id == lead.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
        .options(joinedload(TakeoffLineItem.material_price))
    ).all()
    total_line_count = len(lines_all)
    total_extended = sum(float(x.extended_total or 0) for x in lines_all)
    truncated = False
    lines = list(lines_all)
    if line_limit > 0 and len(lines) > line_limit:
        lines = lines[:line_limit]
        truncated = True
    row_dicts = [_takeoff_line_row(x) for x in lines]
    sections: list[dict[str, Any]] = []
    current_key: str | None = None
    bucket: list[dict[str, Any]] = []
    for row in row_dicts:
        sec = row.get("section") or ""
        key = sec if sec else "(no section)"
        if current_key is None:
            current_key = key
        if key != current_key:
            sections.append({"section": current_key, "lines": bucket})
            bucket = []
            current_key = key
        bucket.append(row)
    if bucket and current_key is not None:
        sections.append({"section": current_key, "lines": bucket})
    ctx = {
        "seller_name": _seller_name(),
        "print_logo_url": _print_logo_url(),
        "doc_title": "Estimate — takeoff summary",
        "lead": _lead_report_header(lead),
        "sections": sections,
        "line_count_total": total_line_count,
        "grand_total": total_extended,
        "truncated": truncated,
        "truncated_note": f"Showing first {line_limit} lines. Open the app for the full takeoff." if truncated else None,
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return render_template("documents/estimate_summary.html", **ctx)


def render_quote_report_html(
    lead: LeadEstimate,
    cu: CurrentUser,
    *,
    columns_raw: str | None = None,
    line_limit: int = 500,
) -> str:
    """Client-facing quote print: letterhead, project + opportunity metadata, column-selectable takeoff."""
    _ = cu
    visible = resolve_visible_columns(columns_raw)
    visible_column_ctx = [
        {
            "id": c.id,
            "label": c.label,
            "row_key": c.row_key,
            "numeric": c.numeric,
            "money": c.id in ("unit_cost", "extended"),
        }
        for c in visible
    ]

    lines_all = db.session.scalars(
        select(TakeoffLineItem)
        .where(TakeoffLineItem.lead_estimate_id == lead.id)
        .order_by(TakeoffLineItem.sort_order.asc(), TakeoffLineItem.created_at.asc())
        .options(joinedload(TakeoffLineItem.material_price))
    ).all()
    total_line_count = len(lines_all)
    total_extended = sum(float(x.extended_total or 0) for x in lines_all)
    truncated = False
    lines = list(lines_all)
    if line_limit > 0 and len(lines) > line_limit:
        lines = lines[:line_limit]
        truncated = True
    row_dicts = [_takeoff_line_quote_row(x) for x in lines]
    sections: list[dict[str, Any]] = []
    current_key: str | None = None
    bucket: list[dict[str, Any]] = []
    for row in row_dicts:
        sec = row.get("section") or ""
        key = sec if sec else "(no section)"
        if current_key is None:
            current_key = key
        if key != current_key:
            sections.append({"section": current_key, "lines": bucket})
            bucket = []
            current_key = key
        bucket.append(row)
    if bucket and current_key is not None:
        sections.append({"section": current_key, "lines": bucket})

    quoter = _self_company_letterhead()
    fallback_seller = _seller_name()

    project_ctx: dict[str, Any] | None = None
    if lead.project_id:
        p = db.session.get(Project, lead.project_id)
        if p is not None and p.deleted_at is None:
            project_ctx = {
                "name": p.name,
                "number": p.number,
                "address": _project_address_lines(p),
                "contract_date": p.contract_date.isoformat() if p.contract_date else None,
                "start_date": p.start_date.isoformat() if p.start_date else None,
            }

    due_at_iso: str | None = None
    if lead.due_at is not None:
        due_at_iso = lead.due_at.isoformat()

    final_value_display: str | None = None
    if lead.final_value is not None:
        final_value_display = f"{float(lead.final_value):,.2f}"

    ctx = {
        "quoter": quoter,
        "fallback_seller_name": fallback_seller,
        "print_logo_url": _print_logo_url(),
        "doc_title": "Quote",
        "lead": _lead_report_header(lead),
        "project": project_ctx,
        "client_company": _client_company_name(lead.client),
        "client_contact": _client_contact_line(lead.client),
        "due_at_iso": due_at_iso,
        "final_value_display": final_value_display,
        "sections": sections,
        "visible_columns": visible_column_ctx,
        "line_count_total": total_line_count,
        "grand_total": total_extended,
        "truncated": truncated,
        "truncated_note": f"Showing first {line_limit} lines. Open the app for the full takeoff." if truncated else None,
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return render_template("documents/quote_report.html", **ctx)


def render_door_schedule_report_html(lead: LeadEstimate, cu: CurrentUser) -> str:
    """Door schedule with per-opening takeoff lines (print)."""
    _ = cu
    openings = db.session.scalars(
        select(DoorOpening)
        .where(DoorOpening.lead_estimate_id == lead.id)
        .order_by(DoorOpening.sort_order.asc(), DoorOpening.created_at.asc())
    ).all()
    items = [_door_opening_report_dict(op) for op in openings]
    grand = sum(float(x.get("extended_total") or 0) for x in items)
    ctx = {
        "seller_name": _seller_name(),
        "print_logo_url": _print_logo_url(),
        "doc_title": "Door schedule",
        "lead": _lead_report_header(lead),
        "openings": items,
        "opening_count": len(items),
        "grand_total": grand,
        "generated_at": datetime.now(tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    return render_template("documents/door_schedule_report.html", **ctx)
