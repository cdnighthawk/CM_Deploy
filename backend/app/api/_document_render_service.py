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

from ..extensions import db
from ..models import Company, Project
from . import _commitment_service as commitment_svc
from ._perms import CurrentUser
from ._rfi_service import ApiError


def _can_view_procurement(cu: CurrentUser) -> bool:
    return (
        cu.is_dev_admin
        or cu.has_role("admin", "superuser", "standard")
        or cu.has_role("read_only", "readonly")
    )


def _seller_name() -> str:
    raw = (current_app.config.get("DOCUMENT_PRINT_COMPANY_NAME") or os.environ.get("DOCUMENT_PRINT_COMPANY_NAME") or "").strip()
    return raw or "USIS Construction Management"


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
        "client_name": client_name,
        "project": _project_public_dict(p),
        "project_address": _project_address_lines(p),
        "scope_text": scope_text,
        "optional_lines": optional_lines,
        "generated_at": date.today().isoformat(),
    }
    return render_template("documents/client_proposal.html", **ctx)
