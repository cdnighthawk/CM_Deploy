"""Send RFP invitations from quotes@ and ingest vendor replies."""
from __future__ import annotations

import os
import re
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import UUID

from flask import current_app
from markupsafe import escape
from sqlalchemy import func, select
from sqlalchemy.orm.attributes import flag_modified
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Company, Contact, Document, Project, Rfp, RfpDrawing, RfpLineItem, RfpVendorQuote
from ..services.object_storage import UploadCategory, save_upload
from ._notifications import (
    GraphMailError,
    download_mailbox_attachment,
    get_mailbox_message,
    list_mailbox_messages,
    public_app_origin,
    send_html_notification_email,
)
from ._rfi_service import ApiError, _iso, _parse_uuid

_KEEP_EXT = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".xlsx", ".xls", ".doc", ".docx"}
)
_SKIP_INLINE_MAX = 20 * 1024
_MAX_QUOTE_PDF = 25 * 1024 * 1024
_TAG_RE = re.compile(r"\[RFP\s+([A-Za-z0-9_-]{6,32})\]", re.IGNORECASE)
_PORTAL_RE = re.compile(r"/public/rfp/([A-Za-z0-9_-]{8,64})", re.IGNORECASE)


def _job_shipping_for_rfp(r: Rfp) -> dict[str, Any]:
    from ._office_location import resolve_job_shipping

    project = db.session.get(Project, r.project_id) if r.project_id else None
    return resolve_job_shipping(project)


def quotes_mailbox() -> str:
    configured = ""
    try:
        configured = str(current_app.config.get("QUOTES_MAILBOX") or "").strip()
    except RuntimeError:
        configured = ""
    if not configured:
        configured = (os.environ.get("QUOTES_MAILBOX") or "quotes@gousis.com").strip()
    return configured or "quotes@gousis.com"


def quotes_from_name() -> str:
    try:
        name = str(current_app.config.get("QUOTES_FROM_NAME") or "").strip()
    except RuntimeError:
        name = ""
    return name or (os.environ.get("QUOTES_FROM_NAME") or "US Interior Specialties").strip() or "US Interior Specialties"


def quotes_bcc_self() -> bool:
    try:
        val = current_app.config.get("RFP_MAIL_BCC_SELF")
    except RuntimeError:
        val = None
    if val is None:
        raw = (os.environ.get("RFP_MAIL_BCC_SELF") or "true").strip().lower()
        return raw not in ("0", "false", "no", "off")
    return bool(val)


def mail_identity() -> dict[str, Any]:
    mailbox = quotes_mailbox()
    return {
        "from_address": mailbox,
        "from_name": quotes_from_name(),
        "reply_to": mailbox,
        "bcc": mailbox if quotes_bcc_self() else None,
        "from_header": f"{quotes_from_name()} <{mailbox}>",
    }


def mailbox_ready() -> bool:
    from ._notifications import _graph_configured

    return _graph_configured()


def new_mail_tag() -> str:
    for _ in range(12):
        tag = secrets.token_urlsafe(8).replace("-", "").replace("_", "")[:10]
        if len(tag) < 8:
            continue
        if db.session.scalar(select(Rfp.id).where(Rfp.mail_tag == tag)) is None:
            return tag
    return secrets.token_urlsafe(12).replace("-", "")[:12]


def ensure_mail_tag(rfp: Rfp) -> str:
    if (rfp.mail_tag or "").strip():
        return rfp.mail_tag.strip()
    rfp.mail_tag = new_mail_tag()
    return rfp.mail_tag


def ensure_invite_token(quote: RfpVendorQuote) -> str:
    if (quote.invite_token or "").strip():
        return quote.invite_token.strip()
    for _ in range(8):
        token = secrets.token_urlsafe(24)[:48]
        if db.session.scalar(select(RfpVendorQuote.id).where(RfpVendorQuote.invite_token == token)) is None:
            quote.invite_token = token
            return token
    quote.invite_token = secrets.token_urlsafe(32)[:64]
    return quote.invite_token


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(raw: Any) -> datetime | None:
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


def _strip_html(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw or "")
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def serialize_quote(q: RfpVendorQuote) -> dict[str, Any]:
    return {
        "id": str(q.id),
        "vendor_label": q.vendor_label,
        "vendor_company_id": str(q.vendor_company_id) if q.vendor_company_id else None,
        "vendor_contact_id": str(q.vendor_contact_id) if q.vendor_contact_id else None,
        "invited_email": q.invited_email,
        "invite_token": q.invite_token,
        "sent_at": _iso(q.sent_at),
        "sent_from_mailbox": q.sent_from_mailbox,
        "source": q.source,
        "from_email": q.from_email,
        "from_name": q.from_name,
        "subject": q.subject,
        "received_at": _iso(q.received_at),
        "mailbox": q.mailbox,
        "line_prices": q.line_prices,
        "lump_sum_amount": float(q.lump_sum_amount) if q.lump_sum_amount is not None else None,
        "vendor_exclusions": q.vendor_exclusions,
        "send_status": q.send_status,
        "notes": q.notes,
        "portal_path": f"/public/rfp/{q.invite_token}" if q.invite_token else None,
        "attachments": [_quote_attachment_public(q, a) for a in (q.attachments or [])],
    }


def _quote_attachment_public(q: RfpVendorQuote, att: Mapping[str, Any] | None) -> dict[str, Any]:
    item = dict(att or {})
    doc_id = item.get("document_id")
    if doc_id:
        item["file_url"] = f"/api/v1/rfps/{q.rfp_id}/quotes/{q.id}/attachments/{doc_id}"
    return item


def serialize_rfp(r: Rfp, *, staff: bool = True) -> dict[str, Any]:
    from ._rfp_award_po import commitment_summary, po_for_rfp
    from ._rfp_body_service import all_line_items, serialize_drawing_row, serialize_line, visible_line_items

    quotes = db.session.scalars(
        select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == r.id).order_by(RfpVendorQuote.created_at)
    ).all()
    staff_lines = all_line_items(r)
    vendor_lines = visible_line_items(r)
    drawings = db.session.scalars(
        select(RfpDrawing).where(RfpDrawing.rfp_id == r.id).order_by(RfpDrawing.sort_order)
    ).all()
    ident = mail_identity()
    return {
        "id": str(r.id),
        "title": r.title,
        "status": r.status,
        "due_at": _iso(r.due_at),
        "sent_at": _iso(r.sent_at),
        "project_id": str(r.project_id) if r.project_id else None,
        "lead_estimate_id": str(r.lead_estimate_id) if r.lead_estimate_id else None,
        "public_token": r.public_token,
        "mail_tag": r.mail_tag,
        "quotes_mailbox": ident["from_address"],
        "from_name": ident["from_name"],
        "from_header": ident["from_header"],
        "line_source": r.line_source or "manual",
        "source_estimate_id": str(r.source_estimate_id) if r.source_estimate_id else None,
        "source_spec_scan_id": str(r.source_spec_scan_id) if getattr(r, "source_spec_scan_id", None) else None,
        "scope_of_work": r.scope_of_work,
        "inclusions": r.inclusions,
        "exclusions": r.exclusions,
        "clarifications": r.clarifications,
        "show_line_table": bool(r.show_line_table),
        "cc_estimator": bool(r.cc_estimator),
        "frozen": not ((r.status or "Draft") == "Draft" and r.sent_at is None),
        "awarded_quote_id": str(r.awarded_quote_id) if getattr(r, "awarded_quote_id", None) else None,
        "commitment": commitment_summary(po_for_rfp(r)),
        "job_shipping": _job_shipping_for_rfp(r),
        "line_items": [serialize_line(x, staff=staff) for x in (staff_lines if staff else vendor_lines)],
        "visible_line_items": [serialize_line(x, staff=False) for x in vendor_lines],
        "drawings": [serialize_drawing_row(d) for d in drawings],
        "quotes": [serialize_quote(q) for q in quotes],
    }


def _refresh_status(rfp: Rfp) -> None:
    quotes = list(rfp.vendor_quotes) if rfp.vendor_quotes is not None else []
    if not quotes:
        quotes = db.session.scalars(select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == rfp.id)).all()
    invited = [q for q in quotes if q.sent_at is not None or (q.source or "") == "invited"]
    received = [q for q in quotes if q.received_at is not None or (q.source or "") in ("portal", "email")]
    if received and invited and len(received) >= len(invited):
        rfp.status = "Received"
    elif received:
        rfp.status = "Partial"
    elif invited and rfp.status == "Draft":
        rfp.status = "Sent"


def _load_rfp(rfp_id: uuid.UUID) -> Rfp:
    r = db.session.get(Rfp, rfp_id)
    if r is None:
        raise ApiError("rfp not found", 404)
    return r


def _resolve_bidder_email(
    company: Company | None, contact: Contact | None, explicit: str | None
) -> str:
    saved: set[str] = set()
    if company is not None:
        for raw in (getattr(company, "quote_email", None), company.email):
            val = (raw or "").strip().lower()
            if val and "@" in val:
                saved.add(val)
        for ct in list(
            db.session.scalars(select(Contact).where(Contact.company_id == company.id)).all()
        ):
            val = (ct.email or "").strip().lower()
            if val and "@" in val:
                saved.add(val)
    if contact is not None:
        val = (contact.email or "").strip().lower()
        if val and "@" in val:
            saved.add(val)
    preferred = ""
    if company is not None:
        preferred = (getattr(company, "quote_email", None) or "").strip().lower()
        if not preferred:
            preferred = (company.email or "").strip().lower()
    if not preferred and contact is not None:
        preferred = (contact.email or "").strip().lower()
    explicit_email = (explicit or "").strip().lower()
    if explicit_email:
        if company is not None and saved and explicit_email not in saved:
            raise ApiError("Add email on the vendor record.")
        if "@" not in explicit_email:
            raise ApiError("bidder is missing an email address")
        return explicit_email[:255]
    if not preferred or "@" not in preferred:
        raise ApiError("bidder is missing an email address")
    return preferred[:255]


def _contact_label(contact: Contact | None, company: Company | None, fallback: str) -> str:
    if contact is not None:
        name = " ".join(p for p in (contact.first_name or "", contact.last_name or "") if p).strip()
        if name:
            return name[:255]
    if company is not None and (company.name or "").strip():
        return company.name.strip()[:255]
    return (fallback or "Vendor")[:255]


def _upsert_bidder(rfp: Rfp, raw: Mapping[str, Any]) -> RfpVendorQuote:
    company_id = _parse_uuid(raw.get("company_id") or raw.get("vendor_company_id"))
    contact_id = _parse_uuid(raw.get("contact_id") or raw.get("vendor_contact_id"))
    explicit_email = str(raw.get("email") or "").strip() or None
    company: Company | None = None
    contact: Contact | None = None
    if company_id:
        company = db.session.get(Company, company_id)
        if company is None or company.deleted_at is not None:
            raise ApiError("company not found", 404)
    if contact_id:
        contact = db.session.get(Contact, contact_id)
        if contact is None:
            raise ApiError("contact not found", 404)
        if company is None and contact.company_id:
            company = db.session.get(Company, contact.company_id)
    email = _resolve_bidder_email(company, contact, explicit_email)
    existing = db.session.scalar(
        select(RfpVendorQuote).where(
            RfpVendorQuote.rfp_id == rfp.id,
            func.lower(RfpVendorQuote.invited_email) == email,
        )
    )
    quote = existing or RfpVendorQuote(rfp_id=rfp.id, source="invited")
    quote.vendor_company_id = company.id if company is not None else quote.vendor_company_id
    quote.vendor_contact_id = contact.id if contact is not None else quote.vendor_contact_id
    quote.invited_email = email
    quote.vendor_label = _contact_label(contact, company, str(raw.get("vendor_label") or "Vendor"))
    ensure_invite_token(quote)
    if existing is None:
        db.session.add(quote)
        db.session.flush()
    return quote


def invite_portal_url(quote: RfpVendorQuote) -> str:
    token = ensure_invite_token(quote)
    return f"{public_app_origin()}/public/rfp/{token}"


def _prewrap_html(label: str, text: str | None) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    return (
        f"<h3 style='font-size:15px;margin:16px 0 6px;color:#1F4E5F'>{escape(label)}</h3>"
        f"<div style='white-space:pre-wrap;font-size:14px'>{escape(body)}</div>"
    )


def _prewrap_text(label: str, text: str | None) -> str:
    body = (text or "").strip()
    if not body:
        return ""
    return f"{label}:\n{body}\n\n"


def drawing_public_url(quote: RfpVendorQuote, row_id: uuid.UUID) -> str:
    token = ensure_invite_token(quote)
    return f"{public_app_origin()}/public/rfp/{token}/files/{row_id}/download"


def files_page_url(quote: RfpVendorQuote, *, redact_token: bool = False) -> str:
    token = ensure_invite_token(quote)
    origin = public_app_origin()
    if redact_token and token:
        return f"{origin}/public/rfp/…{token[-4:]}/files"
    return f"{origin}/public/rfp/{token}/files"


def build_invite_email(
    rfp: Rfp,
    quote: RfpVendorQuote,
    *,
    attached_ids: set[str] | None = None,
    redact_token: bool = False,
) -> tuple[str, str, str]:
    from ._rfp_body_service import serialize_drawing_row, visible_line_items

    ensure_mail_tag(rfp)
    portal = invite_portal_url(quote)
    files_url = files_page_url(quote, redact_token=False)
    files_display = files_page_url(quote, redact_token=redact_token)
    if redact_token and quote.invite_token:
        last4 = quote.invite_token[-4:]
        portal_display = f"{public_app_origin()}/public/rfp/…{last4}"
    else:
        portal_display = portal
    due = ""
    if rfp.due_at:
        due = str(rfp.due_at)[:10]
    lines = visible_line_items(rfp)
    title = (rfp.title or "RFP").strip() or "RFP"
    subject = f"[RFP {rfp.mail_tag}] {title}"[:500]
    ident = mail_identity()

    def qty_cell(x: RfpLineItem) -> str:
        if x.quantity is None:
            return ""
        return f"{float(x.quantity):g}"

    line_table_html = ""
    line_text = ""
    if lines:
        line_rows = "".join(
            f"<tr><td>{escape(x.csi_division or '')}</td><td>{escape(x.description)}</td>"
            f"<td>{qty_cell(x)}</td><td>{escape(x.unit)}</td><td>{escape(x.notes or '')}</td></tr>"
            for x in lines
        )
        line_table_html = (
            "<h3 style='font-size:15px;margin:16px 0 6px;color:#1F4E5F'>Line items</h3>"
            "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse;font-size:14px'>"
            "<thead><tr><th align='left'>CSI</th><th align='left'>Description</th><th>Qty</th><th>Unit</th>"
            "<th align='left'>Notes</th></tr></thead>"
            f"<tbody>{line_rows}</tbody></table>"
        )
        line_text = "Line items:\n" + "\n".join(
            f"- {x.description} ({qty_cell(x)} {x.unit})" for x in lines
        ) + "\n\n"
    drawing_rows = db.session.scalars(
        select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id).order_by(RfpDrawing.sort_order)
    ).all()
    draw_labels: list[str] = []
    for row in drawing_rows:
        meta = serialize_drawing_row(row)
        label = " · ".join(p for p in (meta.get("sheet_number"), meta.get("sheet_title") or meta.get("filename")) if p)
        if label:
            draw_labels.append(label)
    drawings_html = ""
    drawings_text = ""
    files_cta_html = ""
    files_cta_text = ""
    if draw_labels:
        drawings_html = (
            "<h3 style='font-size:15px;margin:16px 0 6px;color:#1F4E5F'>Drawings & specifications</h3>"
            f"<ul>{''.join(f'<li>{escape(label)}</li>' for label in draw_labels)}</ul>"
        )
        drawings_text = "Drawings & specifications:\n" + "\n".join(f"- {label}" for label in draw_labels) + "\n\n"
        files_cta_html = (
            "<p style='margin:20px 0'>"
            f"<a href='{escape(files_url if not redact_token else files_display)}' style='display:inline-block;background:#1F4E5F;color:#fff;"
            "text-decoration:none;padding:12px 18px;border-radius:8px;font-weight:600'>"
            "View drawings &amp; specifications</a></p>"
        )
        files_cta_text = f"View drawings & specifications: {files_display}\n\n"
    due_html = f"<p>Please respond by <strong>{escape(due)}</strong>.</p>" if due else ""
    due_text = f"Please respond by {due}.\n\n" if due else ""
    ship = _job_shipping_for_rfp(rfp)
    ship_addr = (ship.get("shipping_address") or "").strip()
    install = (ship.get("expected_install_date") or "").strip()
    ship_html = ""
    ship_text = ""
    if ship_addr or install:
        ship_bits_html = []
        ship_bits_text = []
        if ship_addr:
            label = ship.get("shipping_label") or "Ship to"
            ship_bits_html.append(
                f"<p style='margin:0 0 6px'><strong>Ship to ({escape(str(label))}):</strong><br>"
                f"<span style='white-space:pre-wrap'>{escape(ship_addr)}</span></p>"
            )
            ship_bits_text.append(f"Ship to ({label}): {ship_addr}")
        if install:
            ship_bits_html.append(f"<p style='margin:0 0 6px'><strong>Expected install date:</strong> {escape(install)}</p>")
            ship_bits_text.append(f"Expected install date: {install}")
        ship_html = (
            "<h3 style='font-size:15px;margin:16px 0 6px;color:#1F4E5F'>Shipping &amp; install</h3>"
            + "".join(ship_bits_html)
        )
        ship_text = "Shipping & install:\n" + "\n".join(ship_bits_text) + "\n\n"
    narrative_html = (
        _prewrap_html("Scope of work", rfp.scope_of_work)
        + _prewrap_html("Inclusions", rfp.inclusions)
        + _prewrap_html("Exclusions", rfp.exclusions)
        + _prewrap_html("Clarifications", rfp.clarifications)
    )
    narrative_text = (
        _prewrap_text("Scope of work", rfp.scope_of_work)
        + _prewrap_text("Inclusions", rfp.inclusions)
        + _prewrap_text("Exclusions", rfp.exclusions)
        + _prewrap_text("Clarifications", rfp.clarifications)
    )
    html = (
        "<html><body style='font-family:Source Sans 3,system-ui,sans-serif;color:#1B242C'>"
        f"<p>Hello {escape(quote.vendor_label)},</p>"
        f"<p>Please submit a quote for <strong>{escape(title)}</strong>.</p>"
        f"{due_html}"
        f"{ship_html}"
        f"{narrative_html}"
        f"{line_table_html}"
        f"{drawings_html}"
        f"{files_cta_html}"
        f"<p style='margin-top:16px'><a href='{escape(portal)}'>Open the vendor portal to submit your quote</a></p>"
        f"<p>You may also reply to this email. Send quotes to {escape(ident['from_address'])} "
        f"and keep <code>[RFP {escape(rfp.mail_tag)}]</code> in the subject.</p>"
        f"<p>Thank you,<br>{escape(ident['from_name'])}</p>"
        "</body></html>"
    )
    text = (
        f"Hello {quote.vendor_label},\n\n"
        f"Please submit a quote for {title}.\n"
        f"{due_text}"
        f"{ship_text}"
        f"{narrative_text}"
        f"{line_text}"
        f"{drawings_text}"
        f"{files_cta_text}"
        f"Vendor portal: {portal_display}\n\n"
        f"You may also reply to this email. Keep [RFP {rfp.mail_tag}] in the subject.\n"
        f"Quotes mailbox: {ident['from_address']}\n"
    )
    return subject, text, html


def send_preview(rfp: Rfp, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    from ._rfp_body_service import content_ready

    payload = data if isinstance(data, Mapping) else {}
    ident = mail_identity()
    ok, errors, warnings = content_ready(rfp)
    quote = db.session.scalars(
        select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == rfp.id).order_by(RfpVendorQuote.created_at)
    ).first()
    preview_quote = quote or RfpVendorQuote(
        rfp_id=rfp.id,
        vendor_label="Vendor",
        invite_token=rfp.public_token,
    )
    subject, text, html = build_invite_email(
        rfp, preview_quote, redact_token=True
    )
    recipients = []
    bidders = payload.get("bidders")
    if isinstance(bidders, list) and bidders:
        for raw in bidders:
            if not isinstance(raw, Mapping):
                continue
            email = str(raw.get("email") or "").strip()
            cid = str(raw.get("company_id") or "")
            missing = not email or "@" not in email
            recipients.append(
                {
                    "company_id": cid or None,
                    "email": email or None,
                    "vendor_label": raw.get("vendor_label") or email,
                    "ready": not missing,
                    "error": "Add email on the vendor record." if missing else None,
                    "company_edit_url": f"usis-companies.html?id={cid}" if cid else None,
                    "token_last4": None,
                }
            )
    else:
        quotes = db.session.scalars(
            select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == rfp.id).order_by(RfpVendorQuote.created_at)
        ).all()
        for q in quotes:
            tok = q.invite_token or ""
            missing = not (q.invited_email or "")
            recipients.append(
                {
                    "quote_id": str(q.id),
                    "company_id": str(q.vendor_company_id) if q.vendor_company_id else None,
                    "email": q.invited_email,
                    "vendor_label": q.vendor_label,
                    "ready": not missing,
                    "error": "Add email on the vendor record." if missing else None,
                    "company_edit_url": (
                        f"usis-companies.html?id={q.vendor_company_id}" if q.vendor_company_id else None
                    ),
                    "token_last4": tok[-4:] if tok else None,
                    "send_status": q.send_status,
                }
            )
    drawings = []
    from ._rfp_body_service import serialize_drawing_row as ser_d

    for row in db.session.scalars(
        select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id).order_by(RfpDrawing.sort_order)
    ).all():
        item = ser_d(row)
        item["will_attach"] = False
        drawings.append(item)
    return {
        "from": ident["from_address"],
        "from_name": ident["from_name"],
        "from_header": ident["from_header"],
        "reply_to": ident["reply_to"],
        "bcc": ident["bcc"],
        "subject": subject,
        "html": html,
        "text": text,
        "due_at": _iso(rfp.due_at),
        "recipients": recipients,
        "drawings": drawings,
        "files_page_cta": files_page_url(preview_quote, redact_token=True),
        "attach_bytes": 0,
        "warnings": warnings,
        "errors": errors,
        "ready": ok and any(r.get("ready") for r in recipients),
        "entity": "rfp_email_preview",
    }


def send_invitations(rfp_id: uuid.UUID, data: Mapping[str, Any] | None, *, user_id: UUID | None = None) -> dict[str, Any]:
    from ._rfp_body_service import content_ready, freeze_drawings_on_send, log_send_audit

    payload = data if isinstance(data, Mapping) else {}
    rfp = _load_rfp(rfp_id)
    ok, errors, warnings = content_ready(rfp)
    if not ok:
        raise ApiError("; ".join(errors))
    bidders = payload.get("bidders")
    quote_ids = payload.get("quote_ids")
    send_all = bool(payload.get("send_all_ready") or payload.get("send_all"))
    quotes_to_send: list[RfpVendorQuote] = []
    sends: list[dict[str, Any]] = []
    if isinstance(bidders, list) and bidders:
        for raw in bidders:
            if not isinstance(raw, Mapping):
                sends.append({"ok": False, "error": "each bidder must be an object"})
                continue
            company = None
            cid = _parse_uuid(raw.get("company_id") or raw.get("vendor_company_id"))
            if cid:
                company = db.session.get(Company, cid)
            if company is not None and not (company.email or "").strip():
                contact_id = _parse_uuid(raw.get("contact_id"))
                contact = db.session.get(Contact, contact_id) if contact_id else None
                contact_email = (contact.email if contact is not None else "") or ""
                if not contact_email and not (raw.get("email") or "").strip():
                    sends.append(
                        {
                            "ok": False,
                            "error": "Add email on the vendor record.",
                            "company_id": str(company.id),
                            "company_edit_url": f"usis-companies.html?id={company.id}",
                        }
                    )
                    continue
            try:
                quotes_to_send.append(_upsert_bidder(rfp, raw))
            except ApiError as exc:
                sends.append({"ok": False, "error": exc.message, "company_id": str(cid) if cid else None})
    elif send_all or (isinstance(quote_ids, list) and quote_ids):
        q = select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == rfp.id)
        if isinstance(quote_ids, list) and quote_ids and not send_all:
            wanted = [_parse_uuid(x) for x in quote_ids]
            wanted = [x for x in wanted if x]
            q = q.where(RfpVendorQuote.id.in_(wanted))
        quotes_to_send = list(db.session.scalars(q.order_by(RfpVendorQuote.created_at)).all())
    else:
        raise ApiError("bidders must be a non-empty list")
    ready = [q for q in quotes_to_send if (q.invited_email or "").strip() and "@" in (q.invited_email or "")]
    blocked = [q for q in quotes_to_send if q not in ready]
    for q in blocked:
        sends.append(
            {
                "ok": False,
                "quote_id": str(q.id),
                "error": "Add email on the vendor record.",
                "company_id": str(q.vendor_company_id) if q.vendor_company_id else None,
                "company_edit_url": (
                    f"usis-companies.html?id={q.vendor_company_id}" if q.vendor_company_id else None
                ),
            }
        )
    if not ready:
        raise ApiError("No vendors with an email address are ready to send.")
    ensure_mail_tag(rfp)
    freeze_drawings_on_send(rfp)
    ident = mail_identity()
    mailbox = ident["from_address"]
    cc_addr = None
    if payload.get("cc_estimator") or rfp.cc_estimator:
        cc_addr = str(payload.get("cc_email") or "").strip() or None
    now = _utcnow()
    sent_ok = False
    drawing_ids = [
        str(r.id)
        for r in db.session.scalars(select(RfpDrawing).where(RfpDrawing.rfp_id == rfp.id)).all()
    ]
    for quote in ready:
        subject, text, html = build_invite_email(rfp, quote)
        result = send_html_notification_email(
            to=quote.invited_email or "",
            subject=subject,
            body=text,
            html_body=html,
            from_addr=mailbox,
            reply_to=mailbox,
            bcc=ident["bcc"],
            cc=cc_addr,
            attachments=None,
            from_name=ident["from_name"],
        )
        ok_send = bool(result.get("sent") or result.get("dry_run"))
        if ok_send:
            quote.sent_at = now
            quote.sent_from_mailbox = mailbox
            quote.send_status = "sent" if result.get("sent") else "queued"
            if not quote.source:
                quote.source = "invited"
            sent_ok = True
            log_send_audit(
                rfp=rfp,
                quote=quote,
                from_email=mailbox,
                drawing_ids=drawing_ids,
                attach_bytes=0,
                message_id=None,
                user_id=user_id,
            )
        else:
            quote.send_status = "bounced"
        sends.append(
            {
                "ok": ok_send,
                "quote_id": str(quote.id),
                "email": quote.invited_email,
                "vendor_label": quote.vendor_label,
                "dry_run": bool(result.get("dry_run")),
                "error": result.get("error"),
            }
        )
    if sent_ok:
        rfp.sent_at = rfp.sent_at or now
        if rfp.status == "Draft":
            rfp.status = "Sent"
    db.session.commit()
    body = {"item": serialize_rfp(rfp), "sends": sends, "entity": "rfp_send"}
    if warnings:
        body["warnings"] = warnings
    return body


def record_portal_quote(
    rfp: Rfp,
    quote: RfpVendorQuote | None,
    *,
    vendor_label: str,
    notes: str | None,
    line_prices: Any | None = None,
    lump_sum_amount: Any | None = None,
    vendor_exclusions: str | None = None,
    pdf_filename: str | None = None,
    pdf_content_type: str | None = None,
    pdf_bytes: bytes | None = None,
) -> RfpVendorQuote:
    from decimal import Decimal, InvalidOperation

    from ._rfp_body_service import rfp_closed, visible_line_items

    if rfp_closed(rfp):
        raise ApiError("This RFP is closed.", 403)
    has_pdf = bool(pdf_bytes)
    if has_pdf:
        _assert_quote_pdf(pdf_filename or "", pdf_content_type or "", pdf_bytes or b"")
    row = quote or RfpVendorQuote(rfp_id=rfp.id)
    row.vendor_label = (vendor_label or row.vendor_label or "Vendor")[:255]
    row.notes = notes
    row.vendor_exclusions = (vendor_exclusions or "").strip() or None
    row.source = "portal"
    row.received_at = row.received_at or _utcnow()
    visible = visible_line_items(rfp)
    if visible:
        parsed: list[dict[str, Any]] = []
        raw_prices = line_prices if isinstance(line_prices, list) else []
        by_id = {
            str(item.get("line_id")): item
            for item in raw_prices
            if isinstance(item, Mapping)
        }
        for ln in visible:
            cell = by_id.get(str(ln.id), {})
            try:
                unit_price = Decimal(str(cell.get("unit_price"))) if cell.get("unit_price") not in (None, "") else None
            except (InvalidOperation, ValueError):
                unit_price = None
            qty = ln.quantity if ln.quantity is not None else Decimal("1")
            extension = (unit_price * qty) if unit_price is not None else None
            parsed.append(
                {
                    "line_id": str(ln.id),
                    "unit_price": float(unit_price) if unit_price is not None else None,
                    "extension": float(extension) if extension is not None else None,
                }
            )
        row.line_prices = parsed
        row.lump_sum_amount = None
        if not has_pdf and not any(p.get("unit_price") is not None for p in parsed):
            raise ApiError("Enter unit prices or attach a PDF quote")
    else:
        try:
            row.lump_sum_amount = (
                Decimal(str(lump_sum_amount)) if lump_sum_amount not in (None, "") else None
            )
        except (InvalidOperation, ValueError):
            raise ApiError("lump_sum_amount must be a number")
        row.line_prices = None
        if row.lump_sum_amount is None and not has_pdf:
            raise ApiError("Enter a lump sum or attach a PDF quote")
    if quote is None or row.id is None:
        db.session.add(row)
    db.session.flush()
    if has_pdf:
        _append_quote_pdf(
            rfp,
            row,
            filename=pdf_filename or "quote.pdf",
            content_type=pdf_content_type or "application/pdf",
            data=pdf_bytes or b"",
            uploaded_by=None,
        )
    _refresh_status(rfp)
    db.session.commit()
    return row


def _match_vendor_company(from_email: str | None, from_name: str | None) -> UUID | None:
    email = (from_email or "").strip().lower()
    if email:
        contact = db.session.scalar(select(Contact).where(func.lower(Contact.email) == email).limit(1))
        if contact is not None and contact.company_id is not None:
            return contact.company_id
        company = db.session.scalar(
            select(Company).where(Company.deleted_at.is_(None), func.lower(Company.email) == email).limit(1)
        )
        if company is not None:
            return company.id
    name = (from_name or "").strip()
    if len(name) >= 3:
        rows = db.session.scalars(
            select(Company).where(
                Company.deleted_at.is_(None),
                Company.company_type.in_(("vendor", "subcontractor", "other")),
                func.lower(Company.name) == name.lower(),
            )
        ).all()
        if len(rows) == 1:
            return rows[0].id
    return None


def _rfp_from_message(subject: str | None, body: str) -> tuple[Rfp | None, RfpVendorQuote | None]:
    hay = f"{subject or ''}\n{body or ''}"
    for match in _TAG_RE.finditer(hay):
        tag = match.group(1)
        rfp = db.session.scalar(select(Rfp).where(Rfp.mail_tag == tag))
        if rfp is not None:
            return rfp, None
    for match in _PORTAL_RE.finditer(hay):
        token = match.group(1)
        quote = db.session.scalar(select(RfpVendorQuote).where(RfpVendorQuote.invite_token == token))
        if quote is not None:
            return db.session.get(Rfp, quote.rfp_id), quote
        rfp = db.session.scalar(select(Rfp).where(Rfp.public_token == token))
        if rfp is not None:
            return rfp, None
    return None, None


def _assert_quote_pdf(filename: str, content_type: str, data: bytes) -> None:
    if not data:
        raise ApiError("empty PDF")
    if len(data) > _MAX_QUOTE_PDF:
        raise ApiError("PDF is too large (max 25 MB)")
    name = (filename or "").lower()
    ctype = (content_type or "").lower()
    if not (name.endswith(".pdf") or "pdf" in ctype):
        raise ApiError("only PDF quotes are accepted")
    if not data.startswith(b"%PDF"):
        raise ApiError("that file does not look like a PDF")


def _append_quote_pdf(
    rfp: Rfp,
    quote: RfpVendorQuote,
    *,
    filename: str,
    content_type: str,
    data: bytes,
    uploaded_by: UUID | None,
) -> dict[str, Any]:
    meta = _store_quote_attachment(
        quote=quote,
        rfp=rfp,
        filename=filename,
        content_type=content_type,
        data=data,
        uploaded_by=uploaded_by,
    )
    atts = list(quote.attachments or [])
    atts.append(meta)
    quote.attachments = atts
    flag_modified(quote, "attachments")
    return meta


def attach_staff_quote_pdf(
    rfp: Rfp,
    *,
    quote_id: UUID | None,
    company_id: UUID | None,
    filename: str,
    content_type: str,
    data: bytes,
    uploaded_by: UUID | None,
) -> dict[str, Any]:
    from ._rfp_body_service import rfp_closed

    if rfp_closed(rfp):
        raise ApiError("This RFP is closed.", 403)
    _assert_quote_pdf(filename, content_type, data)
    quote: RfpVendorQuote | None = None
    if quote_id is not None:
        quote = db.session.get(RfpVendorQuote, quote_id)
        if quote is None or quote.rfp_id != rfp.id:
            raise ApiError("quote not found", 404)
    elif company_id is not None:
        quote = db.session.scalar(
            select(RfpVendorQuote).where(
                RfpVendorQuote.rfp_id == rfp.id,
                RfpVendorQuote.vendor_company_id == company_id,
            )
        )
        if quote is None:
            company = db.session.get(Company, company_id)
            if company is None or company.deleted_at is not None:
                raise ApiError("vendor not found", 404)
            quote = RfpVendorQuote(
                rfp_id=rfp.id,
                vendor_company_id=company.id,
                vendor_label=(company.name or "Vendor")[:255],
                invited_email=(company.email or None),
                source="upload",
            )
            db.session.add(quote)
            db.session.flush()
    if quote is None:
        raise ApiError("pick a vendor for this PDF")
    if not (quote.source or "").strip():
        quote.source = "upload"
    quote.received_at = quote.received_at or _utcnow()
    _append_quote_pdf(
        rfp,
        quote,
        filename=filename,
        content_type=content_type,
        data=data,
        uploaded_by=uploaded_by,
    )
    _refresh_status(rfp)
    db.session.commit()
    return {"item": serialize_quote(quote), "entity": "rfp_vendor_quote"}


def quote_attachment_file(rfp: Rfp, quote_id: UUID, document_id: UUID):
    from ..services.object_storage import UploadCategory, send_stored_file, stored_exists
    from ..services.project_file_keys import document_object_candidates

    quote = db.session.get(RfpVendorQuote, quote_id)
    if quote is None or quote.rfp_id != rfp.id:
        raise ApiError("quote not found", 404)
    known = {str(a.get("document_id")) for a in (quote.attachments or []) if isinstance(a, Mapping)}
    if str(document_id) not in known:
        raise ApiError("attachment not found", 404)
    row = db.session.get(Document, document_id)
    if row is None:
        raise ApiError("attachment not found", 404)
    name = f"{row.id}"
    for cand in document_object_candidates(row):
        if stored_exists(UploadCategory.DOCUMENTS, cand):
            name = cand
            break
    dl = (row.original_filename or row.title or "quote.pdf").replace('"', "")[:200]
    mime = (row.mime_type or "application/pdf").strip() or "application/pdf"
    resp = send_stored_file(
        UploadCategory.DOCUMENTS,
        name,
        mimetype=mime,
        download_name=dl or "quote.pdf",
    )
    if resp is None:
        raise ApiError("file not found on server", 404)
    return resp


def _keep_attachment(name: str, content_type: str, size: int, is_inline: bool) -> bool:
    if is_inline and size and size < _SKIP_INLINE_MAX:
        return False
    ext = ""
    if "." in (name or ""):
        ext = "." + name.rsplit(".", 1)[-1].lower()
    if ext in _KEEP_EXT:
        return True
    ctype = (content_type or "").lower()
    return ctype.startswith("application/pdf") or ctype.startswith("image/")


def _store_quote_attachment(
    *,
    quote: RfpVendorQuote,
    rfp: Rfp,
    filename: str,
    content_type: str,
    data: bytes,
    uploaded_by: UUID | None,
) -> dict[str, Any]:
    raw_name = secure_filename(filename or "attachment") or "attachment"
    ext = ""
    if "." in raw_name:
        ext = "." + raw_name.rsplit(".", 1)[-1].lower()
    if ext not in _KEEP_EXT:
        ext = ".bin"
    doc = Document(
        project_id=rfp.project_id,
        document_type="other",
        title=raw_name[:500],
        original_filename=raw_name[:500],
        mime_type=(content_type or "")[:120] or None,
        file_size_bytes=len(data),
        uploaded_by_user_id=uploaded_by,
        tags={"rfp_vendor_quote_id": str(quote.id), "rfp_id": str(rfp.id), "storage_ext": ext},
    )
    db.session.add(doc)
    db.session.flush()
    object_name = f"{doc.id}{ext}"
    tags = dict(doc.tags or {})
    tags["storage_object"] = object_name
    doc.tags = tags
    flag_modified(doc, "tags")
    save_upload(UploadCategory.DOCUMENTS, object_name, data)
    return {
        "name": raw_name,
        "document_id": str(doc.id),
        "content_type": (content_type or "")[:120] or None,
        "size": len(data),
    }


def ingest_quote_message(
    detail: dict[str, Any],
    *,
    mailbox: str,
    actor_user_id: UUID | None = None,
) -> str | None:
    mid = str(detail.get("id") or "").strip()
    if not mid:
        return None
    existing = db.session.scalar(
        select(RfpVendorQuote).where(RfpVendorQuote.graph_inbound_message_id == mid)
    )
    if existing is not None:
        return None

    from_info = detail.get("from") or {}
    from_email = (from_info.get("address") or "").strip().lower() or None
    from_name = (from_info.get("name") or "").strip() or None
    subject = (detail.get("subject") or "").strip() or None
    body = str(detail.get("body_content") or "")
    preview = (detail.get("preview") or "").strip()
    notes = _strip_html(body) or preview or None
    if notes:
        notes = notes[:8000]

    rfp, quote = _rfp_from_message(subject, body)
    if rfp is None:
        return None

    if quote is None and from_email:
        quote = db.session.scalar(
            select(RfpVendorQuote).where(
                RfpVendorQuote.rfp_id == rfp.id,
                func.lower(RfpVendorQuote.invited_email) == from_email,
            )
        )
    company_id = _match_vendor_company(from_email, from_name)
    if quote is None and company_id is not None:
        quote = db.session.scalar(
            select(RfpVendorQuote).where(
                RfpVendorQuote.rfp_id == rfp.id,
                RfpVendorQuote.vendor_company_id == company_id,
            )
        )
    created = False
    if quote is None:
        quote = RfpVendorQuote(
            rfp_id=rfp.id,
            vendor_label=(from_name or from_email or "Vendor")[:255],
            source="email",
        )
        db.session.add(quote)
        db.session.flush()
        created = True

    quote.graph_inbound_message_id = mid
    quote.from_email = from_email
    quote.from_name = from_name
    quote.subject = (subject or "")[:500] or None
    quote.received_at = _parse_dt(detail.get("received")) or _utcnow()
    quote.mailbox = mailbox
    quote.source = "email"
    quote.notes = notes
    if from_email and not quote.invited_email:
        quote.invited_email = from_email[:255]
    if company_id and not quote.vendor_company_id:
        quote.vendor_company_id = company_id
    if from_name:
        quote.vendor_label = from_name[:255]

    stored_meta: list[dict[str, Any]] = []
    for att in detail.get("attachments") or []:
        if not isinstance(att, dict):
            continue
        name = str(att.get("name") or "attachment")
        ctype = str(att.get("content_type") or att.get("contentType") or "")
        size = int(att.get("size") or 0)
        if not _keep_attachment(name, ctype, size, bool(att.get("is_inline") or att.get("isInline"))):
            continue
        att_id = str(att.get("id") or "")
        if not att_id:
            stored_meta.append({"name": name, "content_type": ctype, "size": size})
            continue
        try:
            data, fname, ftype = download_mailbox_attachment(
                mailbox=mailbox, message_id=mid, attachment_id=att_id
            )
        except GraphMailError:
            stored_meta.append({"name": name, "content_type": ctype, "size": size})
            continue
        stored_meta.append(
            _store_quote_attachment(
                quote=quote,
                rfp=rfp,
                filename=fname or name,
                content_type=ftype or ctype,
                data=data,
                uploaded_by=actor_user_id,
            )
        )
    if stored_meta:
        quote.attachments = stored_meta
    _refresh_status(rfp)
    return "created" if created else "updated"


def sync_quotes_mailbox(*, top: int = 50, actor_user_id: UUID | None = None) -> dict[str, Any]:
    mailbox = quotes_mailbox()
    if not mailbox_ready():
        raise ApiError(
            "Microsoft Graph is not configured. Set MS_ENTRA_TENANT_ID, "
            "MS_ENTRA_CLIENT_ID, and MS_ENTRA_CLIENT_SECRET, and grant Mail.ReadWrite "
            f"on {mailbox}.",
            503,
        )
    listing = list_mailbox_messages(mailbox=mailbox, folder="inbox", top=top)
    created = 0
    updated = 0
    skipped = 0
    unmatched = 0
    errors: list[str] = []
    for item in listing.get("items") or []:
        mid = str(item.get("id") or "")
        if not mid:
            continue
        if db.session.scalar(select(RfpVendorQuote.id).where(RfpVendorQuote.graph_inbound_message_id == mid)):
            skipped += 1
            continue
        try:
            detail = get_mailbox_message(mailbox=mailbox, message_id=mid)
            result = ingest_quote_message(detail, mailbox=mailbox, actor_user_id=actor_user_id)
        except GraphMailError as exc:
            errors.append(f"{mid}: {exc}")
            continue
        except Exception as exc:  # pragma: no cover - unexpected Graph/storage
            errors.append(f"{mid}: {exc}")
            continue
        if result == "created":
            created += 1
        elif result == "updated":
            updated += 1
        else:
            unmatched += 1
    db.session.commit()
    return {
        "mailbox": mailbox,
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "unmatched": unmatched,
        "errors": errors,
    }
