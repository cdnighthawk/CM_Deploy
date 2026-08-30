"""Vendor invoice CRUD, job routing, and payment approval."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import request
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from ..api._perms import CurrentUser
from ..extensions import db
from ..models import Commitment, Company, Document, Project, User
from ..models.vendor_invoice import VendorInvoice, VendorInvoiceFile
from ..permissions.access import has_module_access, module_level
from ..permissions.project_scope import assigned_project_ids, can_see_all_projects, user_can_access_project
from ..services.object_storage import UploadCategory, send_stored_file
from ._events import record_event, utc_now
from ._mailbox import _store_attachment, sync_invoice_mailbox

STATUS_RECEIVED = "received"
STATUS_ROUTED = "routed"
STATUS_PENDING = "pending_approval"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_PAID = "paid"
STATUS_VOID = "void"

EDITABLE_STATUSES = frozenset({STATUS_RECEIVED, STATUS_ROUTED, STATUS_REJECTED})
FILE_MAX_BYTES = 20 * 1024 * 1024
KEEP_EXT = frozenset(
    {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".heic", ".xlsx", ".xls", ".doc", ".docx"}
)


class InvoiceError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _parse_uuid(raw: Any) -> uuid.UUID | None:
    if raw is None or raw == "":
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except (ValueError, TypeError):
        return None


def _parse_date(raw: Any) -> date | None:
    if raw is None or raw == "":
        return None
    try:
        return date.fromisoformat(str(raw).strip()[:10])
    except ValueError:
        return None


def _parse_amount(raw: Any) -> Decimal | None:
    if raw is None or raw == "":
        return None
    try:
        val = Decimal(str(raw).strip().replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError):
        return None
    if val <= 0:
        return None
    return val.quantize(Decimal("0.01"))


def _user_name(u: User | None) -> str:
    if u is None:
        return ""
    return " ".join(p for p in (u.first_name, u.last_name) if p).strip() or (u.email or "")


def _is_finance_approver(cu: CurrentUser) -> bool:
    if cu.is_dev_admin or (cu.user and cu.user.is_superuser):
        return True
    return cu.has_role("admin", "superuser", "executive", "project_accountant") or module_level(cu, "ap") == "admin"


def _can_write(cu: CurrentUser) -> bool:
    return has_module_access(cu, "ap", "write") or cu.is_dev_admin


def _can_view(cu: CurrentUser, invoice: VendorInvoice) -> bool:
    if not has_module_access(cu, "ap", "read") and not cu.is_dev_admin:
        return False
    if invoice.project_id is None:
        return _can_write(cu) or can_see_all_projects(cu)
    return user_can_access_project(cu, invoice.project_id)


def _can_approve(cu: CurrentUser, invoice: VendorInvoice) -> bool:
    if not _can_write(cu):
        return False
    if _is_finance_approver(cu):
        if invoice.project_id is None:
            return True
        return user_can_access_project(cu, invoice.project_id)
    if invoice.project_id is None:
        return False
    return cu.has_role("project_manager") and user_can_access_project(cu, invoice.project_id)


def _can_mark_paid(cu: CurrentUser) -> bool:
    return _is_finance_approver(cu)


def _load(invoice_id: uuid.UUID) -> VendorInvoice | None:
    return db.session.scalar(
        select(VendorInvoice)
        .where(VendorInvoice.id == invoice_id)
        .options(
            selectinload(VendorInvoice.files),
            selectinload(VendorInvoice.events),
        )
    )


def _serialize_file(row: VendorInvoiceFile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "document_id": str(row.document_id),
        "is_primary": bool(row.is_primary),
        "original_filename": row.original_filename,
        "content_type": row.content_type,
        "url": f"/api/v1/ap/invoices/{row.invoice_id}/files/{row.id}/file",
    }


def serialize_invoice(invoice: VendorInvoice, cu: CurrentUser, *, include_events: bool = False) -> dict[str, Any]:
    vendor = db.session.get(Company, invoice.vendor_company_id) if invoice.vendor_company_id else None
    project = db.session.get(Project, invoice.project_id) if invoice.project_id else None
    commitment = db.session.get(Commitment, invoice.commitment_id) if invoice.commitment_id else None
    approver = db.session.get(User, invoice.approver_user_id) if invoice.approver_user_id else None
    files = list(invoice.files) if invoice.files is not None else []
    can_approve = invoice.status == STATUS_PENDING and _can_approve(cu, invoice)
    out: dict[str, Any] = {
        "id": str(invoice.id),
        "status": invoice.status,
        "source": invoice.source,
        "mailbox": invoice.mailbox,
        "from_email": invoice.from_email,
        "from_name": invoice.from_name,
        "subject": invoice.subject,
        "body_preview": invoice.body_preview,
        "received_at": invoice.received_at.isoformat() if invoice.received_at else None,
        "vendor_company_id": str(invoice.vendor_company_id) if invoice.vendor_company_id else None,
        "vendor_name": vendor.name if vendor else None,
        "project_id": str(invoice.project_id) if invoice.project_id else None,
        "project_name": project.name if project else None,
        "project_number": project.number if project else None,
        "commitment_id": str(invoice.commitment_id) if invoice.commitment_id else None,
        "commitment_ref": commitment.reference_number if commitment else None,
        "invoice_number": invoice.invoice_number,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "amount": format(invoice.amount, "f") if invoice.amount is not None else None,
        "currency": invoice.currency,
        "po_number": invoice.po_number,
        "notes": invoice.notes,
        "parse_meta": invoice.parse_meta or {},
        "routed_at": invoice.routed_at.isoformat() if invoice.routed_at else None,
        "submitted_at": invoice.submitted_at.isoformat() if invoice.submitted_at else None,
        "approver_user_id": str(invoice.approver_user_id) if invoice.approver_user_id else None,
        "approver_name": _user_name(approver),
        "decided_at": invoice.decided_at.isoformat() if invoice.decided_at else None,
        "rejection_reason": invoice.rejection_reason,
        "paid_at": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "payment_ref": invoice.payment_ref,
        "files": [_serialize_file(f) for f in files],
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "can_submit": _can_write(cu) and invoice.status in EDITABLE_STATUSES,
        "can_approve": can_approve,
        "can_reject": can_approve,
        "can_mark_paid": invoice.status == STATUS_APPROVED and _can_mark_paid(cu),
    }
    if include_events:
        events = sorted(invoice.events or [], key=lambda e: e.created_at or utc_now())
        out["events"] = [
            {
                "id": str(ev.id),
                "action": ev.action,
                "details": ev.details or {},
                "actor_user_id": str(ev.actor_user_id) if ev.actor_user_id else None,
                "created_at": ev.created_at.isoformat() if ev.created_at else None,
            }
            for ev in events
        ]
    return out


def _visible_query(cu: CurrentUser):
    stmt = select(VendorInvoice)
    allowed = assigned_project_ids(cu)
    if allowed is None:
        return stmt
    if _can_write(cu):
        if allowed:
            return stmt.where(or_(VendorInvoice.project_id.is_(None), VendorInvoice.project_id.in_(allowed)))
        return stmt.where(VendorInvoice.project_id.is_(None))
    if not allowed:
        return stmt.where(VendorInvoice.id.is_(None))
    return stmt.where(VendorInvoice.project_id.in_(allowed))


def list_invoices(cu: CurrentUser, *, status: str | None = None, project_id: uuid.UUID | None = None) -> list[dict[str, Any]]:
    stmt = _visible_query(cu).options(selectinload(VendorInvoice.files)).order_by(
        VendorInvoice.received_at.desc().nullslast(), VendorInvoice.created_at.desc()
    )
    if status:
        stmt = stmt.where(VendorInvoice.status == status)
    if project_id is not None:
        stmt = stmt.where(VendorInvoice.project_id == project_id)
    rows = db.session.scalars(stmt.limit(300)).all()
    return [serialize_invoice(r, cu) for r in rows if _can_view(cu, r)]


def list_approvals(cu: CurrentUser) -> list[dict[str, Any]]:
    items = list_invoices(cu, status=STATUS_PENDING)
    out = []
    for item in items:
        inv = _load(uuid.UUID(item["id"]))
        if inv is not None and _can_approve(cu, inv):
            out.append(item)
    return out


def get_invoice(cu: CurrentUser, invoice_id: uuid.UUID) -> dict[str, Any]:
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    return serialize_invoice(invoice, cu, include_events=True)


def _apply_fields(invoice: VendorInvoice, data: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    if "vendor_company_id" in data:
        vid = _parse_uuid(data.get("vendor_company_id"))
        if vid is not None and db.session.get(Company, vid) is None:
            raise InvoiceError("vendor not found")
        invoice.vendor_company_id = vid
        changed["vendor_company_id"] = str(vid) if vid else None
    if "project_id" in data:
        pid = _parse_uuid(data.get("project_id"))
        if pid is not None:
            if not user_can_access_project(cu, pid):
                raise InvoiceError("project not found or not accessible", 404)
        invoice.project_id = pid
        if pid is not None:
            invoice.routed_at = utc_now()
            invoice.routed_by_user_id = cu.id
            if invoice.status == STATUS_RECEIVED:
                invoice.status = STATUS_ROUTED
        changed["project_id"] = str(pid) if pid else None
    if "commitment_id" in data:
        cid = _parse_uuid(data.get("commitment_id"))
        if cid is not None:
            cmt = db.session.get(Commitment, cid)
            if cmt is None:
                raise InvoiceError("commitment not found")
            invoice.commitment_id = cid
            invoice.project_id = cmt.project_id
            invoice.vendor_company_id = invoice.vendor_company_id or cmt.vendor_company_id
            invoice.po_number = invoice.po_number or cmt.reference_number
            if invoice.status == STATUS_RECEIVED:
                invoice.status = STATUS_ROUTED
                invoice.routed_at = utc_now()
                invoice.routed_by_user_id = cu.id
        else:
            invoice.commitment_id = None
        changed["commitment_id"] = str(cid) if cid else None
    if "invoice_number" in data:
        invoice.invoice_number = (str(data.get("invoice_number") or "").strip() or None)
        changed["invoice_number"] = invoice.invoice_number
    if "invoice_date" in data:
        invoice.invoice_date = _parse_date(data.get("invoice_date"))
        changed["invoice_date"] = invoice.invoice_date.isoformat() if invoice.invoice_date else None
    if "due_date" in data:
        invoice.due_date = _parse_date(data.get("due_date"))
        changed["due_date"] = invoice.due_date.isoformat() if invoice.due_date else None
    if "amount" in data:
        invoice.amount = _parse_amount(data.get("amount"))
        changed["amount"] = format(invoice.amount, "f") if invoice.amount is not None else None
    if "currency" in data:
        cur = str(data.get("currency") or "USD").strip().upper()[:3] or "USD"
        invoice.currency = cur
        changed["currency"] = cur
    if "po_number" in data:
        invoice.po_number = (str(data.get("po_number") or "").strip() or None)
        changed["po_number"] = invoice.po_number
    if "notes" in data:
        invoice.notes = (str(data.get("notes") or "").strip() or None)
        changed["notes"] = invoice.notes
    if "from_email" in data:
        invoice.from_email = (str(data.get("from_email") or "").strip() or None)
    if "from_name" in data:
        invoice.from_name = (str(data.get("from_name") or "").strip() or None)
    if "subject" in data:
        invoice.subject = (str(data.get("subject") or "").strip() or None)[:500] or None
    if invoice.commitment_id:
        from ..api import _purchase_order_fulfillment as po_ful

        cmt = db.session.get(Commitment, invoice.commitment_id)
        if cmt is not None and cmt.commitment_kind == "purchase_order":
            match = po_ful.compute_three_way_match(cmt)
            changed["match_status"] = match.get("matchStatus")
    return changed


def create_invoice(cu: CurrentUser, data: dict[str, Any]) -> dict[str, Any]:
    if not _can_write(cu):
        raise InvoiceError("forbidden", 403)
    invoice = VendorInvoice(
        status=STATUS_RECEIVED,
        source="manual",
        received_at=utc_now(),
        currency="USD",
        parse_meta={},
    )
    _apply_fields(invoice, data, cu)
    db.session.add(invoice)
    db.session.flush()
    record_event(invoice, cu.id, "created", {"source": "manual"})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def update_invoice(cu: CurrentUser, invoice_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    if not _can_write(cu):
        raise InvoiceError("forbidden", 403)
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if invoice.status not in EDITABLE_STATUSES:
        raise InvoiceError("invoice cannot be edited in its current status")
    changed = _apply_fields(invoice, data or {}, cu)
    record_event(invoice, cu.id, "updated", changed)
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def submit_invoice(cu: CurrentUser, invoice_id: uuid.UUID, data: dict[str, Any] | None = None) -> dict[str, Any]:
    if not _can_write(cu):
        raise InvoiceError("forbidden", 403)
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if invoice.status not in {STATUS_RECEIVED, STATUS_ROUTED, STATUS_REJECTED}:
        raise InvoiceError("invoice is not ready for approval")
    if data:
        _apply_fields(invoice, data, cu)
    if invoice.project_id is None:
        raise InvoiceError("route the invoice to a job before submitting")
    if invoice.amount is None:
        raise InvoiceError("enter an invoice amount before submitting")
    invoice.status = STATUS_PENDING
    invoice.submitted_at = utc_now()
    invoice.submitted_by_user_id = cu.id
    invoice.approver_user_id = None
    invoice.decided_at = None
    invoice.rejection_reason = None
    record_event(invoice, cu.id, "submitted", {"project_id": str(invoice.project_id)})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def approve_invoice(cu: CurrentUser, invoice_id: uuid.UUID) -> dict[str, Any]:
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if not _can_approve(cu, invoice):
        raise InvoiceError("forbidden", 403)
    if invoice.status != STATUS_PENDING:
        raise InvoiceError("invoice is not pending approval")
    invoice.status = STATUS_APPROVED
    invoice.approver_user_id = cu.id
    invoice.decided_at = utc_now()
    invoice.rejection_reason = None
    record_event(invoice, cu.id, "approved", {})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def reject_invoice(cu: CurrentUser, invoice_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if not _can_approve(cu, invoice):
        raise InvoiceError("forbidden", 403)
    if invoice.status != STATUS_PENDING:
        raise InvoiceError("invoice is not pending approval")
    reason = str((data or {}).get("reason") or "").strip()
    if not reason:
        raise InvoiceError("rejection reason is required")
    invoice.status = STATUS_REJECTED
    invoice.approver_user_id = cu.id
    invoice.decided_at = utc_now()
    invoice.rejection_reason = reason[:2000]
    record_event(invoice, cu.id, "rejected", {"reason": invoice.rejection_reason})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def mark_paid(cu: CurrentUser, invoice_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    if not _can_mark_paid(cu):
        raise InvoiceError("forbidden", 403)
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if invoice.status != STATUS_APPROVED:
        raise InvoiceError("only approved invoices can be marked paid")
    invoice.status = STATUS_PAID
    invoice.paid_at = utc_now()
    invoice.paid_by_user_id = cu.id
    invoice.payment_ref = (str((data or {}).get("payment_ref") or "").strip() or None)
    record_event(invoice, cu.id, "paid", {"payment_ref": invoice.payment_ref})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def void_invoice(cu: CurrentUser, invoice_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    if not _can_write(cu):
        raise InvoiceError("forbidden", 403)
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if invoice.status in {STATUS_PAID, STATUS_VOID}:
        raise InvoiceError("invoice cannot be voided")
    reason = str((data or {}).get("reason") or "").strip()
    invoice.status = STATUS_VOID
    invoice.notes = "\n".join(p for p in (invoice.notes, f"Voided: {reason}" if reason else "Voided") if p)
    record_event(invoice, cu.id, "voided", {"reason": reason or None})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def sync_mailbox(cu: CurrentUser) -> dict[str, Any]:
    if not _can_write(cu):
        raise InvoiceError("forbidden", 403)
    try:
        result = sync_invoice_mailbox(actor_user_id=cu.id)
    except RuntimeError as exc:
        raise InvoiceError(str(exc), 503) from exc
    except Exception as exc:
        from ..api._notifications import GraphMailError

        if isinstance(exc, GraphMailError):
            raise InvoiceError(str(exc), 502) from exc
        raise
    db.session.commit()
    return result


def upload_file(cu: CurrentUser, invoice_id: uuid.UUID) -> dict[str, Any]:
    if not _can_write(cu):
        raise InvoiceError("forbidden", 403)
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    if invoice.status not in EDITABLE_STATUSES:
        raise InvoiceError("files cannot be added in the current status")
    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        raise InvoiceError("missing file field (multipart form-data)")
    raw_name = secure_filename(f.filename) or "attachment"
    ext = ""
    if "." in raw_name:
        ext = "." + raw_name.rsplit(".", 1)[-1].lower()
    if ext not in KEEP_EXT:
        raise InvoiceError(f"unsupported file type; allowed: {', '.join(sorted(KEEP_EXT))}")
    cl = request.content_length
    if cl is not None and cl > FILE_MAX_BYTES:
        raise InvoiceError("file too large (max 20MB)")
    data = f.read()
    if len(data) > FILE_MAX_BYTES:
        raise InvoiceError("file too large (max 20MB)")
    has_primary = any(x.is_primary for x in (invoice.files or []))
    _store_attachment(
        invoice=invoice,
        filename=raw_name,
        content_type=f.mimetype or "",
        data=data,
        is_primary=not has_primary,
        uploaded_by=cu.id,
    )
    record_event(invoice, cu.id, "file_added", {"filename": raw_name})
    db.session.commit()
    return serialize_invoice(_load(invoice.id) or invoice, cu, include_events=True)


def send_file(cu: CurrentUser, invoice_id: uuid.UUID, file_id: uuid.UUID):
    invoice = _load(invoice_id)
    if invoice is None or not _can_view(cu, invoice):
        raise InvoiceError("invoice not found", 404)
    row = next((x for x in (invoice.files or []) if x.id == file_id), None)
    if row is None:
        raise InvoiceError("file not found", 404)
    doc = db.session.get(Document, row.document_id)
    if doc is None:
        raise InvoiceError("file not found", 404)
    tags = doc.tags if isinstance(doc.tags, dict) else {}
    ext = str(tags.get("storage_ext") or "")
    if not ext and doc.original_filename and "." in doc.original_filename:
        ext = "." + doc.original_filename.rsplit(".", 1)[-1].lower()
    resp = send_stored_file(
        UploadCategory.AP_INVOICE,
        f"{doc.id}{ext}",
        mimetype=doc.mime_type or "application/octet-stream",
        download_name=row.original_filename or doc.original_filename or "invoice",
    )
    if resp is None:
        raise InvoiceError("file missing from storage", 404)
    return resp


def list_vendors(q: str | None = None) -> list[dict[str, Any]]:
    stmt = select(Company).where(
        Company.deleted_at.is_(None),
        Company.company_type.in_(("vendor", "subcontractor", "other", "gc")),
    ).order_by(Company.name.asc()).limit(300)
    rows = db.session.scalars(stmt).all()
    needle = (q or "").strip().lower()
    if needle:
        rows = [c for c in rows if needle in (c.name or "").lower()]
    return [{"id": str(c.id), "name": c.name, "company_type": c.company_type} for c in rows[:80]]


def list_projects(cu: CurrentUser, q: str | None = None) -> list[dict[str, Any]]:
    from ..permissions.project_scope import project_access_clause

    stmt = select(Project).where(Project.deleted_at.is_(None), project_access_clause(cu)).order_by(
        Project.number.asc().nullslast(), Project.name.asc()
    )
    rows = db.session.scalars(stmt.limit(400)).all()
    needle = (q or "").strip().lower()
    out = []
    for p in rows:
        label = " — ".join(x for x in (p.number, p.name) if x)
        if needle and needle not in label.lower() and needle not in (p.name or "").lower():
            continue
        out.append({"id": str(p.id), "name": p.name, "number": p.number, "label": label or p.name})
        if len(out) >= 80:
            break
    return out


def list_commitments(cu: CurrentUser, project_id: uuid.UUID | None, vendor_id: uuid.UUID | None) -> list[dict[str, Any]]:
    stmt = select(Commitment)
    if project_id is not None:
        if not user_can_access_project(cu, project_id):
            raise InvoiceError("project not found or not accessible", 404)
        stmt = stmt.where(Commitment.project_id == project_id)
    else:
        allowed = assigned_project_ids(cu)
        if allowed is not None:
            if not allowed:
                return []
            stmt = stmt.where(Commitment.project_id.in_(allowed))
    if vendor_id is not None:
        stmt = stmt.where(Commitment.vendor_company_id == vendor_id)
    rows = db.session.scalars(stmt.order_by(Commitment.reference_number.asc().nullslast()).limit(80)).all()
    return [
        {
            "id": str(c.id),
            "project_id": str(c.project_id),
            "vendor_company_id": str(c.vendor_company_id),
            "reference_number": c.reference_number,
            "title": c.title,
            "status": c.status,
        }
        for c in rows
    ]
