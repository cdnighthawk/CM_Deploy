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
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import Company, Contact, Document, Rfp, RfpLineItem, RfpVendorQuote
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
_TAG_RE = re.compile(r"\[RFP\s+([A-Za-z0-9_-]{6,32})\]", re.IGNORECASE)
_PORTAL_RE = re.compile(r"/public/rfp/([A-Za-z0-9_-]{8,64})", re.IGNORECASE)


def quotes_mailbox() -> str:
    configured = ""
    try:
        configured = str(current_app.config.get("QUOTES_MAILBOX") or "").strip()
    except RuntimeError:
        configured = ""
    if not configured:
        configured = (os.environ.get("QUOTES_MAILBOX") or "quotes@gousis.com").strip()
    return configured or "quotes@gousis.com"


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
        "attachments": q.attachments or [],
        "notes": q.notes,
        "portal_path": f"/public/rfp/{q.invite_token}" if q.invite_token else None,
    }


def serialize_rfp(r: Rfp) -> dict[str, Any]:
    lines = db.session.scalars(
        select(RfpLineItem).where(RfpLineItem.rfp_id == r.id).order_by(RfpLineItem.sort_order)
    ).all()
    quotes = db.session.scalars(
        select(RfpVendorQuote).where(RfpVendorQuote.rfp_id == r.id).order_by(RfpVendorQuote.created_at)
    ).all()
    return {
        "id": str(r.id),
        "title": r.title,
        "status": r.status,
        "due_at": _iso(r.due_at),
        "sent_at": _iso(r.sent_at),
        "public_token": r.public_token,
        "mail_tag": r.mail_tag,
        "quotes_mailbox": quotes_mailbox(),
        "line_items": [
            {
                "id": str(x.id),
                "description": x.description,
                "quantity": float(x.quantity),
                "unit": x.unit,
            }
            for x in lines
        ],
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
    email = (explicit or "").strip().lower()
    if not email and contact is not None:
        email = (contact.email or "").strip().lower()
    if not email and company is not None:
        email = (company.email or "").strip().lower()
    if not email or "@" not in email:
        raise ApiError("bidder is missing an email address")
    return email[:255]


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


def build_invite_email(rfp: Rfp, quote: RfpVendorQuote) -> tuple[str, str, str]:
    ensure_mail_tag(rfp)
    portal = invite_portal_url(quote)
    due = ""
    if rfp.due_at:
        due = str(rfp.due_at)[:10]
    lines = db.session.scalars(
        select(RfpLineItem).where(RfpLineItem.rfp_id == rfp.id).order_by(RfpLineItem.sort_order)
    ).all()
    title = (rfp.title or "RFP").strip() or "RFP"
    subject = f"[RFP {rfp.mail_tag}] {title}"[:500]
    line_rows = "".join(
        f"<tr><td>{escape(x.description)}</td><td>{float(x.quantity):g}</td><td>{escape(x.unit)}</td></tr>"
        for x in lines
    )
    line_text = "\n".join(f"- {x.description} ({float(x.quantity):g} {x.unit})" for x in lines) or "(no line items)"
    due_html = f"<p>Please respond by <strong>{escape(due)}</strong>.</p>" if due else ""
    due_text = f"Please respond by {due}.\n\n" if due else ""
    html = (
        "<html><body style='font-family:Source Sans 3,system-ui,sans-serif;color:#1B242C'>"
        f"<p>Hello {escape(quote.vendor_label)},</p>"
        f"<p>Please submit a quote for <strong>{escape(title)}</strong>.</p>"
        f"{due_html}"
        "<table cellpadding='6' cellspacing='0' border='1' style='border-collapse:collapse;font-size:14px'>"
        "<thead><tr><th align='left'>Description</th><th>Qty</th><th>Unit</th></tr></thead>"
        f"<tbody>{line_rows or '<tr><td colspan=3>No line items</td></tr>'}</tbody></table>"
        f"<p style='margin-top:16px'><a href='{escape(portal)}'>Open the vendor portal to submit your quote</a></p>"
        f"<p>You may also reply to this email. Send quotes to {escape(quotes_mailbox())} "
        f"and keep <code>[RFP {escape(rfp.mail_tag)}]</code> in the subject.</p>"
        "<p>Thank you,<br>US Interior Specialties</p>"
        "</body></html>"
    )
    text = (
        f"Hello {quote.vendor_label},\n\n"
        f"Please submit a quote for {title}.\n"
        f"{due_text}"
        f"Line items:\n{line_text}\n\n"
        f"Vendor portal: {portal}\n\n"
        f"You may also reply to this email. Keep [RFP {rfp.mail_tag}] in the subject.\n"
        f"Quotes mailbox: {quotes_mailbox()}\n"
    )
    return subject, text, html


def send_invitations(rfp_id: uuid.UUID, data: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = data if isinstance(data, Mapping) else {}
    bidders = payload.get("bidders")
    if not isinstance(bidders, list) or not bidders:
        raise ApiError("bidders must be a non-empty list")
    rfp = _load_rfp(rfp_id)
    ensure_mail_tag(rfp)
    mailbox = quotes_mailbox()
    sends: list[dict[str, Any]] = []
    now = _utcnow()
    sent_ok = False
    for raw in bidders:
        if not isinstance(raw, Mapping):
            sends.append({"ok": False, "error": "each bidder must be an object"})
            continue
        try:
            quote = _upsert_bidder(rfp, raw)
        except ApiError as exc:
            sends.append({"ok": False, "error": exc.message})
            continue
        subject, text, html = build_invite_email(rfp, quote)
        result = send_html_notification_email(
            to=quote.invited_email or "",
            subject=subject,
            body=text,
            html_body=html,
            from_addr=mailbox,
            reply_to=mailbox,
        )
        ok = bool(result.get("sent") or result.get("dry_run"))
        if ok:
            quote.sent_at = now
            quote.sent_from_mailbox = mailbox
            if not quote.source:
                quote.source = "invited"
            sent_ok = True
        sends.append(
            {
                "ok": ok,
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
    return {"item": serialize_rfp(rfp), "sends": sends, "entity": "rfp_send"}


def record_portal_quote(
    rfp: Rfp,
    quote: RfpVendorQuote | None,
    *,
    vendor_label: str,
    notes: str | None,
) -> RfpVendorQuote:
    row = quote or RfpVendorQuote(rfp_id=rfp.id)
    row.vendor_label = (vendor_label or row.vendor_label or "Vendor")[:255]
    row.notes = notes
    row.source = "portal"
    row.received_at = row.received_at or _utcnow()
    if quote is None:
        db.session.add(row)
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
    save_upload(UploadCategory.DOCUMENTS, f"{doc.id}{ext}", data)
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
