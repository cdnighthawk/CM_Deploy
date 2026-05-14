"""Public vendor-facing RFP routes (no /api/v1 prefix)."""
from __future__ import annotations

from flask import Blueprint, request
from sqlalchemy import select

from .extensions import db
from .models import Rfp, RfpVendorQuote

public_bp = Blueprint("public_portal", __name__)


def _rfp_by_token(token: str) -> Rfp | None:
    raw = (token or "").strip()
    if not raw:
        return None
    return db.session.scalar(select(Rfp).where(Rfp.public_token == raw))


@public_bp.get("/public/rfp/<token>")
def public_rfp_get(token: str):
    r = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    lines = list(r.line_items)
    rows = "".join(
        f"<tr><td>{x.description}</td><td>{float(x.quantity)}</td><td>{x.unit}</td></tr>" for x in lines
    )
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>{r.title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet"></head>
    <body class="p-4"><div class="container"><h1>{r.title}</h1>
    <p class="text-muted">Submit a quote using the form below.</p>
    <table class="table table-sm"><thead><tr><th>Description</th><th>Qty</th><th>Unit</th></tr></thead><tbody>{rows}</tbody></table>
    <form method="post" class="mt-4"><div class="mb-3"><label class="form-label">Vendor name</label>
    <input name="vendor_label" class="form-control" required></div>
    <div class="mb-3"><label class="form-label">Notes</label><textarea name="notes" class="form-control" rows="3"></textarea></div>
    <button class="btn btn-primary" type="submit">Submit quote</button></form></div></body></html>"""
    return html


@public_bp.post("/public/rfp/<token>")
def public_rfp_post(token: str):
    r = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    vendor = (request.form.get("vendor_label") or "Vendor").strip()[:255]
    notes = (request.form.get("notes") or "").strip() or None
    q = RfpVendorQuote(rfp_id=r.id, vendor_label=vendor, notes=notes, line_prices={})
    db.session.add(q)
    db.session.commit()
    return "<p>Thank you — quote received.</p>", 200
