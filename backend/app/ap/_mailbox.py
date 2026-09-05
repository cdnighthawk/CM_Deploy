"""Read invoices@ mailbox via Microsoft Graph and create vendor invoice rows."""
from __future__ import annotations

import os
import re
import threading
import time
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
from ._parse import (
    extract_forwarded_origin,
    extract_invoice_fields,
    looks_like_forward,
    normalize_org_name,
)

_KEEP_EXT = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".xlsx", ".xls", ".doc", ".docx"}
)
_ATTACH_MAX_BYTES = 20 * 1024 * 1024
_SYNC_LOCK = threading.Lock()


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


def _internal_domains() -> set[str]:
    domains = {"gousis.com"}
    try:
        raw = str(current_app.config.get("MAIL_ALLOWED_FROM_DOMAINS") or "")
        domains.update(p.strip().lower() for p in raw.split(",") if p.strip())
    except RuntimeError:
        pass
    mailbox = invoice_mailbox().lower()
    if "@" in mailbox:
        domains.add(mailbox.rsplit("@", 1)[-1])
    return {d for d in domains if d}


def _is_internal_address(email: str | None) -> bool:
    addr = (email or "").strip().lower()
    if "@" not in addr:
        return False
    return addr.rsplit("@", 1)[-1] in _internal_domains()


def _match_vendor(from_email: str | None, from_name: str | None) -> UUID | None:
    email = (from_email or "").strip().lower()
    if email and not _is_internal_address(email):
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
        types = ("vendor", "subcontractor", "other", "gc")
        rows = db.session.scalars(
            select(Company).where(
                Company.deleted_at.is_(None),
                Company.company_type.in_(types),
                func.lower(Company.name) == name.lower(),
            ).limit(2)
        ).all()
        if rows:
            return rows[0].id
        needle = normalize_org_name(name)
        if len(needle) >= 4:
            candidates = db.session.scalars(
                select(Company).where(
                    Company.deleted_at.is_(None),
                    Company.company_type.in_(types),
                ).limit(2000)
            ).all()
            hits = [c for c in candidates if normalize_org_name(c.name) == needle]
            if hits:
                return hits[0].id
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
    if is_inline:
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


def _message_fields(detail: dict[str, Any]) -> dict[str, Any]:
    from_info = detail.get("from") or {}
    envelope_email = (from_info.get("address") or "").strip() or None
    envelope_name = (from_info.get("name") or "").strip() or None
    subject = (detail.get("subject") or "").strip() or None
    body = str(detail.get("body_content") or "")
    preview = (detail.get("preview") or "")[:2000] or None
    parsed = extract_invoice_fields(subject, body)
    origin = extract_forwarded_origin(subject, body, skip_domains=_internal_domains())
    parsed["forwarded"] = origin
    parsed["envelope_from"] = envelope_email
    parsed["envelope_from_name"] = envelope_name

    from_email = envelope_email
    from_name = envelope_name
    has_origin = bool(origin.get("email") or origin.get("company") or origin.get("name"))
    employee_forward = _is_internal_address(envelope_email) and has_origin
    if employee_forward or (origin.get("is_forward") and has_origin):
        if origin.get("email"):
            from_email = str(origin["email"])
        from_name = origin.get("company") or origin.get("name") or from_name

    vendor_id = _match_vendor(from_email, from_name)
    if vendor_id is None and origin.get("company"):
        vendor_id = _match_vendor(None, str(origin["company"]))
    if vendor_id is None and origin.get("name"):
        vendor_id = _match_vendor(from_email, str(origin["name"]))

    amount = None
    if parsed.get("amount"):
        try:
            amount = Decimal(str(parsed["amount"]))
        except Exception:
            amount = None
    return {
        "from_email": from_email,
        "from_name": from_name,
        "subject": subject,
        "body": body,
        "preview": preview,
        "parsed": parsed,
        "vendor_id": vendor_id,
        "amount": amount,
        "origin": origin,
    }


def _should_enrich(invoice: VendorInvoice) -> bool:
    meta = invoice.parse_meta if isinstance(invoice.parse_meta, dict) else {}
    if meta.get("deleted"):
        return False
    if invoice.source != "email" or invoice.status not in {"received", "routed"}:
        return False
    if _is_internal_address(invoice.from_email):
        return True
    forwarded = meta.get("forwarded") if isinstance(meta, dict) else None
    if isinstance(forwarded, dict) and forwarded.get("email"):
        return False
    return looks_like_forward(invoice.subject, invoice.body_preview)


def _enrich_from_detail(invoice: VendorInvoice, detail: dict[str, Any]) -> bool:
    fields = _message_fields(detail)
    changed = False
    if fields["from_email"] and fields["from_email"] != invoice.from_email:
        invoice.from_email = fields["from_email"]
        changed = True
    if fields["from_name"] and fields["from_name"] != invoice.from_name:
        invoice.from_name = fields["from_name"]
        changed = True
    if invoice.vendor_company_id is None and fields["vendor_id"] is not None:
        invoice.vendor_company_id = fields["vendor_id"]
        changed = True
    if invoice.invoice_number is None and fields["parsed"].get("invoice_number"):
        invoice.invoice_number = fields["parsed"].get("invoice_number")
        changed = True
    if invoice.amount is None and fields["amount"] is not None:
        invoice.amount = fields["amount"]
        changed = True
    if invoice.po_number is None and fields["parsed"].get("po_number"):
        invoice.po_number = fields["parsed"].get("po_number")
        changed = True
    meta = dict(invoice.parse_meta or {})
    meta.update(fields["parsed"])
    invoice.parse_meta = meta
    if not invoice.body_preview:
        invoice.body_preview = fields["preview"] or (fields["parsed"].get("text_sample") or "")[:2000] or None
    return changed


def ingest_graph_message(
    detail: dict[str, Any],
    *,
    mailbox: str,
    actor_user_id: UUID | None = None,
    existing: VendorInvoice | None = None,
) -> VendorInvoice | None:
    mid = str(detail.get("id") or "").strip()
    if not mid:
        return None
    if existing is None:
        existing = db.session.scalar(select(VendorInvoice).where(VendorInvoice.graph_message_id == mid))
    if existing is not None:
        return existing if _enrich_from_detail(existing, detail) else None

    fields = _message_fields(detail)
    commitment_id, commitment_project_id = _match_commitment(
        fields["parsed"].get("po_number"), fields["vendor_id"]
    )
    project_id = commitment_project_id or _match_project(
        list(fields["parsed"].get("job_tokens") or []), fields["subject"]
    )
    status = "routed" if project_id else "received"
    now = datetime.now(timezone.utc)

    invoice = VendorInvoice(
        status=status,
        source="email",
        graph_message_id=mid,
        mailbox=mailbox,
        from_email=fields["from_email"],
        from_name=fields["from_name"],
        subject=fields["subject"],
        body_preview=fields["preview"] or (fields["parsed"].get("text_sample") or "")[:2000] or None,
        received_at=_parse_dt(detail.get("received")) or now,
        vendor_company_id=fields["vendor_id"],
        project_id=project_id,
        commitment_id=commitment_id,
        invoice_number=fields["parsed"].get("invoice_number"),
        amount=fields["amount"],
        po_number=fields["parsed"].get("po_number"),
        parse_meta=fields["parsed"],
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
        if size and size > _ATTACH_MAX_BYTES:
            continue
        att_id = str(att.get("id") or "")
        if not att_id:
            continue
        try:
            data, fname, ftype = download_mailbox_attachment(
                mailbox=mailbox, message_id=mid, attachment_id=att_id
            )
            _store_attachment(
                invoice=invoice,
                filename=fname or name,
                content_type=ftype or ctype,
                data=data,
                is_primary=stored == 0,
                uploaded_by=actor_user_id,
            )
            stored += 1
        except GraphMailError:
            continue
        except Exception:
            current_app.logger.exception("Invoice attachment store failed for %s", mid)
            continue

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
            "auto_vendor": bool(fields["vendor_id"]),
        },
    )
    return invoice


def _sync_limits(max_new: int | None, budget_sec: float | None) -> tuple[int, float]:
    cfg_new = 8
    cfg_budget = 70.0
    try:
        cfg_new = int(current_app.config.get("INVOICE_MAILBOX_SYNC_MAX_NEW") or 8)
        cfg_budget = float(current_app.config.get("INVOICE_MAILBOX_SYNC_BUDGET_SEC") or 70)
    except (RuntimeError, TypeError, ValueError):
        pass
    if max_new is not None:
        cfg_new = int(max_new)
    if budget_sec is not None:
        cfg_budget = float(budget_sec)
    return max(1, cfg_new), max(5.0, cfg_budget)


def sync_invoice_mailbox(
    *,
    top: int = 50,
    actor_user_id: UUID | None = None,
    max_new: int | None = None,
    budget_sec: float | None = None,
) -> dict[str, Any]:
    mailbox = invoice_mailbox()
    if not mailbox_ready():
        raise RuntimeError(
            "Microsoft Graph is not configured. Set MS_ENTRA_TENANT_ID, "
            "MS_ENTRA_CLIENT_ID, and MS_ENTRA_CLIENT_SECRET, and grant Mail.Read "
            f"on {mailbox}."
        )
    if not _SYNC_LOCK.acquire(blocking=False):
        return {
            "mailbox": mailbox,
            "scanned": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": [],
            "busy": True,
            "truncated": False,
        }
    try:
        return _sync_invoice_mailbox_locked(
            mailbox=mailbox,
            top=top,
            actor_user_id=actor_user_id,
            max_new=max_new,
            budget_sec=budget_sec,
        )
    finally:
        _SYNC_LOCK.release()


def _sync_invoice_mailbox_locked(
    *,
    mailbox: str,
    top: int,
    actor_user_id: UUID | None,
    max_new: int | None,
    budget_sec: float | None,
) -> dict[str, Any]:
    limit_new, limit_sec = _sync_limits(max_new, budget_sec)
    deadline = time.monotonic() + limit_sec
    listing = list_mailbox_messages(mailbox=mailbox, folder="inbox", top=top)
    created = 0
    updated = 0
    skipped = 0
    truncated = False
    errors: list[str] = []
    items = listing.get("items") or []
    for idx, item in enumerate(items):
        if time.monotonic() >= deadline:
            truncated = True
            break
        mid = str(item.get("id") or "")
        if not mid:
            continue
        existing = db.session.scalar(select(VendorInvoice).where(VendorInvoice.graph_message_id == mid))
        if existing is not None and not _should_enrich(existing):
            skipped += 1
            continue
        if created >= limit_new and not (existing is not None and _should_enrich(existing)):
            truncated = True
            break
        try:
            with db.session.begin_nested():
                detail = get_mailbox_message(mailbox=mailbox, message_id=mid)
                invoice = ingest_graph_message(
                    detail, mailbox=mailbox, actor_user_id=actor_user_id, existing=existing
                )
                if invoice is None:
                    skipped += 1
                    continue
                if existing is not None:
                    updated += 1
                else:
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
        if created >= limit_new and idx + 1 < len(items):
            truncated = True
    return {
        "mailbox": mailbox,
        "scanned": len(listing.get("items") or []),
        "created": created,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "busy": False,
        "truncated": truncated,
    }
