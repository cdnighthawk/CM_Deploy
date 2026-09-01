"""Public vendor-facing RFP routes (no /api/v1 prefix)."""
from __future__ import annotations

from flask import Blueprint, request
from markupsafe import escape
from sqlalchemy import select

from .api._rfp_quotes_service import record_portal_quote
from .extensions import db
from .models import Rfp, RfpVendorQuote

public_bp = Blueprint("public_portal", __name__)

_PUBLIC_CHROME = """
<link href="https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@400;600;650;700&display=swap" rel="stylesheet">
<style>
:root{--usis-primary:#1F4E5F;--usis-bg:#F4F6F8;--usis-paper:#fff;--usis-text:#1B242C;--usis-muted:#5C6B76;--usis-line:#E3E8EE}
body.usis-public-rfp{font-family:"Source Sans 3",system-ui,sans-serif;background:var(--usis-bg);color:var(--usis-text);margin:0}
.usis-public-rfp-header{background:var(--usis-paper);border-bottom:1px solid var(--usis-line);padding:12px 16px}
.usis-public-rfp-header strong{font-size:1.125rem}
.usis-public-rfp .wrap{max-width:40rem;margin:0 auto;padding:24px 16px}
.usis-public-rfp .card-like{background:var(--usis-paper);border:1px solid var(--usis-line);border-radius:10px;padding:16px}
.usis-public-rfp h1{font-size:1.375rem;font-weight:650;margin:0 0 .35rem}
.usis-public-rfp .muted{color:var(--usis-muted);font-size:.8125rem}
.usis-public-rfp .form-control,.usis-public-rfp .form-select{font-size:.8125rem;border-radius:8px}
.usis-public-rfp .btn-primary{background:var(--usis-primary);border-color:var(--usis-primary);font-weight:600;border-radius:8px;width:100%}
.usis-public-rfp .table{font-size:.8125rem}
.usis-chip{display:inline-flex;align-items:center;height:24px;padding:0 .55rem;border:1px solid var(--usis-line);border-radius:999px;font-size:12px;font-weight:600;color:var(--usis-muted)}
</style>
"""


def _rfp_by_token(token: str) -> tuple[Rfp | None, RfpVendorQuote | None]:
    raw = (token or "").strip()
    if not raw:
        return None, None
    quote = db.session.scalar(select(RfpVendorQuote).where(RfpVendorQuote.invite_token == raw))
    if quote is not None:
        return db.session.get(Rfp, quote.rfp_id), quote
    rfp = db.session.scalar(select(Rfp).where(Rfp.public_token == raw))
    return rfp, None


@public_bp.get("/public/rfp/<token>")
def public_rfp_get(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    lines = list(r.line_items)
    rows = "".join(
        f"<tr><td>{escape(x.description)}</td><td>{float(x.quantity)}</td><td>{escape(x.unit)}</td></tr>"
        for x in lines
    )
    due = getattr(r, "due_at", None) or getattr(r, "due_date", None) or ""
    vendor_val = escape(quote.vendor_label) if quote and quote.vendor_label else ""
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(r.title)}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    {_PUBLIC_CHROME}</head>
    <body class="usis-public-rfp">
    <header class="usis-public-rfp-header d-flex justify-content-between align-items-center gap-2">
      <strong>US Interior Specialties</strong>
      <span class="usis-chip">RFP{(' · due ' + str(due)[:10]) if due else ''}</span>
    </header>
    <div class="wrap"><div class="card-like">
    <h1>{escape(r.title)}</h1>
    <p class="muted mb-3">Submit a quote using the form below.</p>
    <table class="table table-sm"><thead><tr><th>Description</th><th>Qty</th><th>Unit</th></tr></thead><tbody>{rows}</tbody></table>
    <form method="post" class="mt-3"><div class="mb-3"><label class="form-label">Vendor name</label>
    <input name="vendor_label" class="form-control form-control-sm" value="{vendor_val}" required></div>
    <div class="mb-3"><label class="form-label">Notes</label><textarea name="notes" class="form-control form-control-sm" rows="3"></textarea></div>
    <button class="btn btn-primary" type="submit">Submit quote</button></form>
    </div></div></body></html>"""
    return html


@public_bp.post("/public/rfp/<token>")
def public_rfp_post(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    vendor = (request.form.get("vendor_label") or "Vendor").strip()[:255]
    notes = (request.form.get("notes") or "").strip() or None
    record_portal_quote(r, quote, vendor_label=vendor, notes=notes)
    return (
        f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Quote received</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
        {_PUBLIC_CHROME}</head>
        <body class="usis-public-rfp"><div class="wrap"><div class="card-like">
        <h1>Quote received</h1>
        <p class="muted mb-0">Thank you — we have your response.</p>
        </div></div></body></html>""",
        200,
    )


@public_bp.post("/api/public/submittals/<token>")
def public_submittal_upload(token: str):
    from flask import jsonify

    from .api._rfi_service import ApiError
    from .api import _submittal_qc as qc

    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        return jsonify(qc.public_upload(token, data)), 201
    except ApiError as exc:
        return jsonify({"error": exc.message}), exc.status


@public_bp.get("/public/submittals/<token>")
def public_submittal_form(token: str):
    from sqlalchemy import select

    from .models import Submittal

    s = db.session.scalar(select(Submittal).where(Submittal.public_token == token))
    if s is None:
        return "<p>Submittal not found</p>", 404
    title = s.title
    number = s.submittal_number or f"#{s.number}"
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{number}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    {_PUBLIC_CHROME}</head>
    <body class="usis-public-rfp">
    <header class="usis-public-rfp-header d-flex justify-content-between align-items-center gap-2">
      <strong>US Interior Specialties</strong>
      <span class="usis-chip">{number}</span>
    </header>
    <div class="wrap"><div class="card-like">
    <h1>{number}</h1>
    <p class="muted mb-3">{title}</p>
    <p class="muted">Upload product data for this package only. You cannot see other vendors.</p>
    <form method="post" action="/api/public/submittals/{token}" class="mt-3">
    <div class="mb-3"><label class="form-label">Vendor name</label>
    <input name="vendor_label" class="form-control form-control-sm" required></div>
    <div class="mb-3"><label class="form-label">File URL</label>
    <input name="file_url" class="form-control form-control-sm" required placeholder="https://…/cutsheet.pdf"></div>
    <div class="mb-3"><label class="form-label">Notes</label>
    <textarea name="notes" class="form-control form-control-sm" rows="3"></textarea></div>
    <button class="btn btn-primary" type="submit">Upload package</button></form>
    </div></div></body></html>"""
