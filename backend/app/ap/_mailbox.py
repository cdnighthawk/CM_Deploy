"""Read invoices@ mailbox via Microsoft Graph and create vendor invoice rows."""
from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from flask import current_app
from sqlalchemy import func, or_, select
from werkzeug.utils import secure_filename

from ..api._notifications import (
    GraphMailError,
    download_mailbox_attachment,
    get_mailbox_message,
    list_mailbox_messages,
    mark_mailbox_message_read,
)
from ..extensions import db
from ..models import Commitment, Company, Contact, Document, Project
from ..models.vendor_invoice import VendorInvoice, VendorInvoiceFile
from ..services.object_storage import UploadCategory, save_upload
from ._parse import extract_invoice_fields

_KEEP_EXT = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".xlsx", ".xls", ".doc", ".docx"}
)
_SKIP_INLINE_MAX = 20 * 1024


def invoice_mailbox() -> str:
    configured = ""
    try:
        configured = str(current_app.config.get("INVOICE_MAILBOX") or "").strip()
    except RuntimeError:
        configured = ""
    if not configured:
        configured = (os.environ.get("INVOICE_MAILBOX") or "invoices@gousis.com").strip()
    return configured or "invoices@gousis.com"


def mailbox_ready() -> bool:
    from ..api._notifications import _graph_credentials_present

    return _graph_credentials_present()


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


def _match_vendor(from_email: str | None, from_name: str | None) -> UUID | None:
    email = (from_email or "").strip().lower()
    if email:
        contact = db.session.scalar(
            select(Contact).where(func.lower(Contact.email) == email).limit(1)
        )
        if contact is not None and contact.company_id is not None:
            return contact.company_id
        company = db.session.scalar(
            select(Company).where(
                Company.deleted_at.is_(None),
                func.lower(Company.email) == email,
            ).limit(1)
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


def _match_project(job_tokens: list[str], subject: str | None) -> UUID | None:
    tokens = [t.strip() for t in job_tokens if t and t.strip()]
    hay = (subject or "").strip()
    if hay:
        for proj in db.session.scalars(
            select(Project).where(Project.deleted_at.is_(None), Project.number.is_not(None))
        ).all():
            num = (proj.number or "").strip()
            if num and re.search(rf"(?<![A-Za-z0-9]){re.escape(num)}(?![A-Za-z0-9])", hay):
                tokens.append(num)
    seen: set[str] = set()
    uniq: list[str] = []
    for t in tokens:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(t)
    matches: list[Project] = []
    for token in uniq:
        rows = db.session.scalars(
            select(Project).where(
                Project.deleted_at.is_(None),
                or_(
                    func.lower(Project.number) == token.lower(),
                    func.lower(Project.name) == token.lower(),
                ),
            )
        ).all()
        matches.extend(rows)
    ids = {p.id for p in matches}
    if len(ids) == 1:
        return next(iter(ids))
    return None


def _match_commitment(po_number: str | None, vendor_id: UUID | None) -> tuple[UUID | None, UUID | None]:
    po = (po_number or "").strip()
    if not po:
        return None, None
    stmt = select(Commitment).where(func.lower(Commitment.reference_number) == po.lower())
    if vendor_id is not None:
        stmt = stmt.where(Commitment.vendor_company_id == vendor_id)
    rows = db.session.scalars(stmt.limit(3)).all()
    if len(rows) == 1:
        return rows[0].id, rows[0].project_id
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


def _store_attachment(
    *,
    invoice: VendorInvoice,
    filename: str,
    content_type: str,
    data: bytes,
    is_primary: bool,
    uploaded_by: UUID | None,
) -> None:
    raw_name = secure_filename(filename or "attachment") or "attachment"
    ext = ""
    if "." in raw_name:
        ext = "." + raw_name.rsplit(".", 1)[-1].lower()
    if ext not in _KEEP_EXT:
        ext = ".bin"
    doc = Document(
        project_id=invoice.project_id,
        document_type="other",
        title=raw_name[:500],
        original_filename=raw_name[:500],
        mime_type=(content_type or "")[:120] or None,
        file_size_bytes=len(data),
        uploaded_by_user_id=uploaded_by,
        tags={"vendor_invoice_id": str(invoice.id), "storage_ext": ext},
    )
    db.session.add(doc)
    db.session.flush()
    save_upload(UploadCategory.AP_INVOICE, f"{doc.id}{ext}", data)
    db.session.add(
        VendorInvoiceFile(
            invoice_id=invoice.id,
            document_id=doc.id,
            is_primary=is_primary,
            original_filename=raw_name[:500],
            content_type=(content_type or "")[:120] or None,
        )
    )


def ingest_graph_message(
    detail: dict[str, Any],
    *,
    mailbox: str,
    actor_user_id: UUID | None = None,
) -> VendorInvoice | None:
    mid = str(detail.get("id") or "").strip()
    if not mid:
        return None
    existing = db.session.scalar(select(VendorInvoice).where(VendorInvoice.graph_message_id == mid))
    if existing is not None:
        return None

    from_info = detail.get("from") or {}
    from_email = (from_info.get("address") or "").strip() or None
    from_name = (from_info.get("name") or "").strip() or None
    subject = (detail.get("subject") or "").strip() or None
    body = str(detail.get("body_content") or "")
    preview = (detail.get("preview") or "")[:2000] or None
    parsed = extract_invoice_fields(subject, body)
    vendor_id = _match_vendor(from_email, from_name)
    amount = None
    if parsed.get("amount"):
        try:
            amount = Decimal(str(parsed["amount"]))
        except Exception:
            amount = None
    commitment_id, commitment_project_id = _match_commitment(parsed.get("po_number"), vendor_id)
    project_id = commitment_project_id or _match_project(list(parsed.get("job_tokens") or []), subject)
    status = "routed" if project_id else "received"
    now = datetime.now(timezone.utc)

    invoice = VendorInvoice(
        status=status,
        source="email",
        graph_message_id=mid,
        mailbox=mailbox,
        from_email=from_email,
        from_name=from_name,
        subject=subject,
        body_preview=preview or (parsed.get("text_sample") or "")[:2000] or None,
        received_at=_parse_dt(detail.get("received")) or now,
        vendor_company_id=vendor_id,
        project_id=project_id,
        commitment_id=commitment_id,
        invoice_number=parsed.get("invoice_number"),
        amount=amount,
        po_number=parsed.get("po_number"),
        parse_meta=parsed,
        routed_at=now if project_id else None,
        routed_by_user_id=actor_user_id if project_id else None,
    )
    db.session.add(invoice)
    db.session.flush()

    attachments = [a for a in (detail.get("attachments") or []) if isinstance(a, dict)]
    stored = 0
    for att in attachments:
        name = str(att.get("name") or "attachment")
        ctype = str(att.get("content_type") or "")
        size = int(att.get("size") or 0)
        if not _keep_attachment(name, ctype, size, bool(att.get("is_inline"))):
            continue
        att_id = str(att.get("id") or "")
        if not att_id:
            continue
        try:
            data, fname, ftype = download_mailbox_attachment(
                mailbox=mailbox, message_id=mid, attachment_id=att_id
            )
        except GraphMailError:
            continue
        _store_attachment(
            invoice=invoice,
            filename=fname or name,
            content_type=ftype or ctype,
            data=data,
            is_primary=stored == 0,
            uploaded_by=actor_user_id,
        )
        stored += 1

    from ._events import record_event

    record_event(
        invoice,
        actor_user_id,
        "received",
        {
            "source": "email",
            "mailbox": mailbox,
            "attachment_count": stored,
            "auto_project": bool(project_id),
            "auto_vendor": bool(vendor_id),
        },
    )
    return invoice


def sync_invoice_mailbox(*, top: int = 50, actor_user_id: UUID | None = None) -> dict[str, Any]:
    mailbox = invoice_mailbox()
    if not mailbox_ready():
        raise RuntimeError(
            "Microsoft Graph is not configured. Set MS_ENTRA_TENANT_ID, "
            "MS_ENTRA_CLIENT_ID, and MS_ENTRA_CLIENT_SECRET, and grant Mail.Read "
            f"on {mailbox}."
        )
    listing = list_mailbox_messages(mailbox=mailbox, folder="inbox", top=top)
    created = 0
    skipped = 0
    errors: list[str] = []
    for item in listing.get("items") or []:
        mid = str(item.get("id") or "")
        if not mid:
            continue
        if db.session.scalar(select(VendorInvoice.id).where(VendorInvoice.graph_message_id == mid)):
            skipped += 1
            continue
        try:
            with db.session.begin_nested():
                detail = get_mailbox_message(mailbox=mailbox, message_id=mid)
                invoice = ingest_graph_message(detail, mailbox=mailbox, actor_user_id=actor_user_id)
                if invoice is None:
                    skipped += 1
                    continue
                created += 1
                try:
                    mark_mailbox_message_read(mailbox=mailbox, message_id=mid, is_read=True)
                except GraphMailError:
                    pass
        except GraphMailError as exc:
            errors.append(str(exc))
        except Exception as exc:
            current_app.logger.exception("Invoice mailbox ingest failed for %s", mid)
            errors.append(f"{mid}: {exc}")
    return {
        "mailbox": mailbox,
        "scanned": len(listing.get("items") or []),
        "created": created,
        "skipped": skipped,
        "errors": errors,
    }
