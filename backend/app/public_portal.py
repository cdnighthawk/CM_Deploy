"""Public vendor-facing RFP routes (no /api/v1 prefix)."""
from __future__ import annotations

from uuid import UUID

from flask import Blueprint, redirect, render_template, request
from markupsafe import escape
from sqlalchemy import func, select

from .api._rfi_service import ApiError
from .api._rfp_body_service import rfp_closed, serialize_drawing_row, visible_line_items
from .api._rfp_quotes_service import record_portal_quote
from .extensions import db
from .models import Company, Project, Rfp, RfpDrawing, RfpVendorQuote
from .services.rfp_b2 import (
    authorized_download_response,
    enqueue_zip,
    log_download,
    zip_download_response,
)

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
.usis-public-rfp h2{font-size:1rem;font-weight:650;margin:1.1rem 0 .4rem;color:var(--usis-primary)}
.usis-public-rfp .muted{color:var(--usis-muted);font-size:.8125rem}
.usis-public-rfp .prewrap{white-space:pre-wrap}
.usis-public-rfp .form-control,.usis-public-rfp .form-select{font-size:.8125rem;border-radius:8px}
.usis-public-rfp .btn-primary{background:var(--usis-primary);border-color:var(--usis-primary);font-weight:600;border-radius:8px;width:100%}
.usis-public-rfp .btn-outline-primary{color:var(--usis-primary);border-color:var(--usis-primary);font-weight:600;border-radius:8px}
.usis-public-rfp .table{font-size:.8125rem}
.usis-chip{display:inline-flex;align-items:center;height:24px;padding:0 .55rem;border:1px solid var(--usis-line);border-radius:999px;font-size:12px;font-weight:600;color:var(--usis-muted)}
.usis-public-rfp a{color:var(--usis-primary)}
.usis-drop{border:1.5px dashed var(--usis-line);border-radius:10px;padding:18px 12px;text-align:center;background:#fafbfc;cursor:pointer}
.usis-drop.is-drag{border-color:var(--usis-primary);background:#eef5f7}
.usis-drop strong{display:block;font-size:.9rem}

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


def _closed_page(r: Rfp) -> tuple[str, int]:
    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{escape(r.title or "RFP")}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    {_PUBLIC_CHROME}</head>
    <body class="usis-public-rfp"><div class="wrap"><div class="card-like">
    <h1>This request is closed</h1>
    <p class="muted mb-0">The due date has passed or the RFP is no longer accepting quotes.</p>
    </div></div></body></html>"""
    return html, 403


def _narrative_html(r: Rfp) -> str:
    parts = []
    for label, val in (
        ("Scope of work", r.scope_of_work),
        ("Inclusions", r.inclusions),
        ("Exclusions", r.exclusions),
        ("Clarifications", r.clarifications),
    ):
        if (val or "").strip():
            parts.append(f"<h2>{escape(label)}</h2><div class='prewrap'>{escape(val)}</div>")
    return "".join(parts)


def _invitation_blocked(r: Rfp, quote: RfpVendorQuote | None) -> bool:
    if rfp_closed(r):
        return True
    if quote is not None and (quote.send_status or "").lower() in ("revoked", "cancelled", "canceled"):
        return True
    return False


def _fmt_size(n: int | None) -> str:
    if not n:
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f" {n / 1024:.0f} KB".strip()
    return f"{n / (1024 * 1024):.1f} MB"


def _drawings_html(r: Rfp, token: str) -> str:
    n = db.session.scalar(
        select(func.count())
        .select_from(RfpDrawing)
        .where(RfpDrawing.rfp_id == r.id, RfpDrawing.include_on_portal.is_(True))
    ) or 0
    if int(n) < 1:
        return ""
    href = f"/public/rfp/{escape(token)}/files"
    return (
        "<p class='mt-3 mb-0'><a class='btn btn-outline-primary w-100' href='"
        f"{href}'>Drawings &amp; specifications</a></p>"
    )


@public_bp.get("/public/rfp/<token>")
def public_rfp_get(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    if _invitation_blocked(r, quote):
        return _closed_page(r)
    lines = visible_line_items(r)
    if lines:
        rows = "".join(
            (
                "<tr>"
                f"<td>{escape(x.description)}</td>"
                f"<td>{'' if x.quantity is None else float(x.quantity)}</td>"
                f"<td>{escape(x.unit)}</td>"
                f"<td><input name='price_{x.id}' class='form-control form-control-sm' type='number' step='0.01' min='0'></td>"
                "</tr>"
            )
            for x in lines
        )
        pricing = f"""<table class="table table-sm"><thead><tr><th>Description</th><th>Qty</th><th>Unit</th><th>Unit price</th></tr></thead><tbody>{rows}</tbody></table>"""
    else:
        pricing = """<div class="mb-3"><label class="form-label">Lump sum</label>
        <input name="lump_sum_amount" class="form-control form-control-sm" type="number" step="0.01" min="0"></div>
        <div class="mb-3"><label class="form-label">Your exclusions</label>
        <textarea name="vendor_exclusions" class="form-control form-control-sm" rows="2"></textarea></div>"""
    due = getattr(r, "due_at", None) or ""
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
    <p class="muted mb-3">Submit a quote using the form below. You can drop a PDF quote instead of filling prices.</p>
    {_narrative_html(r)}
    {_drawings_html(r, token)}
    <form method="post" enctype="multipart/form-data" class="mt-3"><div class="mb-3"><label class="form-label">Vendor name</label>
    <input name="vendor_label" class="form-control form-control-sm" value="{vendor_val}" required></div>
    {pricing}
    <div class="mb-3"><label class="form-label">Quote PDF</label>
    <label class="usis-drop d-block mb-0" id="usis-quote-drop">
      <input name="quote_pdf" id="usis-quote-pdf" type="file" accept="application/pdf,.pdf" class="d-none">
      <strong>Drop your quote PDF here</strong>
      <span class="muted" id="usis-quote-pdf-name">or click to browse · PDF only</span>
    </label></div>
    <div class="mb-3"><label class="form-label">Notes</label><textarea name="notes" class="form-control form-control-sm" rows="3"></textarea></div>
    <button class="btn btn-primary" type="submit">Submit quote</button></form>
    </div></div>
    <script>
    (function(){{
      var drop = document.getElementById("usis-quote-drop");
      var input = document.getElementById("usis-quote-pdf");
      var label = document.getElementById("usis-quote-pdf-name");
      if (!drop || !input) return;
      function show(file) {{
        if (label) label.textContent = file && file.name ? file.name : "or click to browse · PDF only";
      }}
      drop.addEventListener("dragover", function (ev) {{ ev.preventDefault(); drop.classList.add("is-drag"); }});
      drop.addEventListener("dragleave", function () {{ drop.classList.remove("is-drag"); }});
      drop.addEventListener("drop", function (ev) {{
        ev.preventDefault();
        drop.classList.remove("is-drag");
        var file = ev.dataTransfer && ev.dataTransfer.files && ev.dataTransfer.files[0];
        if (!file) return;
        var ok = /pdf$/i.test(file.name || "") || (file.type || "") === "application/pdf";
        if (!ok) {{ if (label) label.textContent = "PDF only"; return; }}
        var dt = new DataTransfer();
        dt.items.add(file);
        input.files = dt.files;
        show(file);
      }});
      input.addEventListener("change", function () {{ show(input.files && input.files[0]); }});
    }})();
    </script>
    </body></html>"""
    return html


@public_bp.post("/public/rfp/<token>")
def public_rfp_post(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    if _invitation_blocked(r, quote):
        return _closed_page(r)
    vendor = (request.form.get("vendor_label") or "Vendor").strip()[:255]
    notes = (request.form.get("notes") or "").strip() or None
    exclusions = (request.form.get("vendor_exclusions") or "").strip() or None
    lump = request.form.get("lump_sum_amount")
    line_prices = []
    for key, val in request.form.items():
        if key.startswith("price_") and val not in (None, ""):
            line_prices.append({"line_id": key[6:], "unit_price": val})
    pdf = request.files.get("quote_pdf")
    pdf_bytes = pdf.read() if pdf is not None and getattr(pdf, "filename", None) else None
    try:
        record_portal_quote(
            r,
            quote,
            vendor_label=vendor,
            notes=notes,
            line_prices=line_prices or None,
            lump_sum_amount=lump,
            vendor_exclusions=exclusions,
            pdf_filename=(pdf.filename if pdf is not None else None),
            pdf_content_type=(pdf.mimetype if pdf is not None else None),
            pdf_bytes=pdf_bytes or None,
        )
    except ApiError as exc:
        if exc.status == 403:
            return _closed_page(r)
        return f"<p>{escape(exc.message)}</p>", exc.status
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


@public_bp.get("/public/rfp/<token>/files")
def public_rfp_files(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    if _invitation_blocked(r, quote):
        html, status = _closed_page(r)
        return html, status
    rows_db = db.session.scalars(
        select(RfpDrawing)
        .where(RfpDrawing.rfp_id == r.id, RfpDrawing.include_on_portal.is_(True))
        .order_by(RfpDrawing.sort_order)
    ).all()
    rows = []
    for row in rows_db:
        meta = serialize_drawing_row(row)
        rows.append(
            {
                "sheet": meta.get("sheet_number") or "—",
                "title": meta.get("sheet_title") or meta.get("filename") or "File",
                "rev": meta.get("revision") or "—",
                "size": _fmt_size(meta.get("bytes")),
                "download_url": f"/public/rfp/{token}/files/{row.id}/download",
            }
        )
    job = ""
    if r.project_id:
        proj = db.session.get(Project, r.project_id)
        if proj is not None:
            job = proj.name or ""
    vendor = ""
    if quote is not None:
        vendor = quote.vendor_label or ""
        if quote.vendor_company_id:
            co = db.session.get(Company, quote.vendor_company_id)
            if co is not None:
                vendor = co.name or vendor
    due = str(r.due_at)[:10] if r.due_at else ""
    return render_template(
        "public/rfp_files.html",
        title=r.title or "RFP",
        job=job,
        vendor=vendor,
        due=due,
        rows=rows,
        zip_url=f"/public/rfp/{token}/files/zip",
        quote_url=f"/public/rfp/{token}",
    )


@public_bp.get("/public/rfp/<token>/files/<row_id>/download")
def public_rfp_file_download(token: str, row_id: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    if _invitation_blocked(r, quote):
        return "<p>Download is no longer available.</p>", 403
    try:
        rid = UUID(str(row_id))
    except ValueError:
        return "<p>Drawing not found</p>", 404
    row = db.session.get(RfpDrawing, rid)
    if row is None or row.rfp_id != r.id or not row.include_on_portal:
        return "<p>Drawing not found</p>", 404
    result = authorized_download_response(row)
    failed = isinstance(result, tuple) and len(result) == 2 and int(result[1]) >= 400
    if not failed:
        log_download(
            rfp=r,
            row=row,
            company_id=quote.vendor_company_id if quote is not None else None,
            bytes_count=row.byte_size or row.frozen_bytes,
            ip=request.headers.get("X-Forwarded-For", request.remote_addr),
        )
    return result


@public_bp.post("/public/rfp/<token>/files/zip")
def public_rfp_files_zip_enqueue(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    if _invitation_blocked(r, quote):
        return "<p>Download is no longer available.</p>", 403
    result = enqueue_zip(r)
    if result.get("status") == "ready":
        return redirect(f"/public/rfp/{token}/files/zip", code=302)
    return (
        "<p>Preparing zip… <a href='/public/rfp/"
        f"{escape(token)}/files/zip'>Download when ready</a></p>",
        202,
    )


@public_bp.get("/public/rfp/<token>/files/zip")
def public_rfp_files_zip_get(token: str):
    r, quote = _rfp_by_token(token)
    if r is None:
        return "<p>RFP not found</p>", 404
    if _invitation_blocked(r, quote):
        return "<p>Download is no longer available.</p>", 403
    return zip_download_response(r)


@public_bp.get("/public/rfp/<token>/drawings/<row_id>")
def public_rfp_drawing(token: str, row_id: str):
    return redirect(f"/public/rfp/{token}/files/{row_id}/download", code=302)


@public_bp.post("/api/public/submittals/<token>")
def public_submittal_upload(token: str):
    from flask import jsonify

    from .api._rfi_service import ApiError as SubApiError
    from .api import _submittal_qc as qc

    data = request.get_json(silent=True) or request.form.to_dict()
    try:
        return jsonify(qc.public_upload(token, data)), 201
    except SubApiError as exc:
        return jsonify({"error": exc.message}), exc.status


@public_bp.get("/public/submittals/<token>")
def public_submittal_form(token: str):
    from sqlalchemy import select as sel

    from .models import Submittal

    s = db.session.scalar(sel(Submittal).where(Submittal.public_token == token))
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
