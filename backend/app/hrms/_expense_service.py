"""HRMS employee expense reports — CRUD, receipts, approvals, reimbursement."""
from __future__ import annotations

import csv
import io
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from flask import Blueprint, Response, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from werkzeug.utils import secure_filename

from ..api._perms import CurrentUser, current_user
from ..extensions import db
from ..models import Document, Project, User
from ..models.hrms_core import HrmsEmployeeProfile, HrmsExpenseLine, HrmsExpenseReport
from ..permissions.project_scope import project_access_clause, user_can_access_project
from ..services.hr_hire_upload import HR_HIRE_DOC_EXT, resolve_hire_doc_upload
from ..services.object_storage import UploadCategory, delete_stored, save_upload, send_stored_file
from ._audit import write_hrms_audit
from ._perms import is_hr_admin, is_hr_manager

EXPENSE_STATUS_DRAFT = "draft"
EXPENSE_STATUS_SUBMITTED = "submitted"
EXPENSE_STATUS_APPROVED = "approved"
EXPENSE_STATUS_REJECTED = "rejected"
EXPENSE_STATUS_REIMBURSED = "reimbursed"

EXPENSE_STATUSES = frozenset(
    {
        EXPENSE_STATUS_DRAFT,
        EXPENSE_STATUS_SUBMITTED,
        EXPENSE_STATUS_APPROVED,
        EXPENSE_STATUS_REJECTED,
        EXPENSE_STATUS_REIMBURSED,
    }
)

EXPENSE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("travel", "Travel"),
    ("meals", "Meals"),
    ("tools", "Tools & equipment"),
    ("fuel", "Fuel"),
    ("lodging", "Lodging"),
    ("other", "Other"),
)

REceipt_MAX_BYTES = 10 * 1024 * 1024


class ExpenseError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _json_error(msg: str, code: int = 400):
    from flask import jsonify

    return jsonify({"error": msg, "entity": "hrms_expense"}), code


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


def _receipt_storage_ext(doc: Document | None) -> str | None:
    if doc is None:
        return None
    tags = doc.tags if isinstance(doc.tags, dict) else {}
    ext = tags.get("receipt_ext")
    if ext:
        return str(ext)
    if doc.original_filename and "." in doc.original_filename:
        return "." + doc.original_filename.rsplit(".", 1)[-1].lower()
    return None


def _receipt_file_url(report_id: uuid.UUID, line_id: uuid.UUID) -> str:
    return f"/api/v1/hrms/expense-reports/{report_id}/lines/{line_id}/receipt/file"


def _serialize_line(line: HrmsExpenseLine, *, report_id: uuid.UUID | None = None) -> dict[str, Any]:
    proj = line.project if hasattr(line, "project") and line.project is not None else None
    if proj is None and line.project_id:
        proj = db.session.get(Project, line.project_id)
    rid = report_id or line.report_id
    has_receipt = line.receipt_document_id is not None
    return {
        "id": str(line.id),
        "report_id": str(rid),
        "project_id": str(line.project_id),
        "project_name": proj.name if proj else None,
        "project_number": proj.number if proj else None,
        "spent_at": line.spent_at.isoformat(),
        "amount": format(line.amount, "f"),
        "currency": line.currency,
        "category": line.category,
        "merchant": line.merchant,
        "description": line.description,
        "receipt_document_id": str(line.receipt_document_id) if line.receipt_document_id else None,
        "receipt_url": _receipt_file_url(rid, line.id) if has_receipt else None,
    }


def _serialize_report(report: HrmsExpenseReport, *, include_lines: bool = True) -> dict[str, Any]:
    owner = report.user if hasattr(report, "user") and report.user is not None else db.session.get(User, report.user_id)
    approver = None
    if report.approver_user_id:
        approver = db.session.get(User, report.approver_user_id)
    lines_out: list[dict[str, Any]] = []
    total = Decimal("0")
    if include_lines:
        lines = list(report.lines) if hasattr(report, "lines") and report.lines else []
        if not lines:
            lines = db.session.scalars(
                select(HrmsExpenseLine).where(HrmsExpenseLine.report_id == report.id).order_by(HrmsExpenseLine.spent_at)
            ).all()
        for ln in lines:
            lines_out.append(_serialize_line(ln, report_id=report.id))
            total += ln.amount
    return {
        "id": str(report.id),
        "user_id": str(report.user_id),
        "employee_name": _user_name(owner),
        "employee_email": owner.email if owner else None,
        "title": report.title,
        "currency": report.currency,
        "status": report.status,
        "submitted_at": report.submitted_at.isoformat() if report.submitted_at else None,
        "approver_user_id": str(report.approver_user_id) if report.approver_user_id else None,
        "approver_name": _user_name(approver),
        "decided_at": report.decided_at.isoformat() if report.decided_at else None,
        "rejection_reason": report.rejection_reason,
        "exported_at": report.exported_at.isoformat() if report.exported_at else None,
        "export_batch_id": str(report.export_batch_id) if report.export_batch_id else None,
        "reimbursed_at": report.reimbursed_at.isoformat() if report.reimbursed_at else None,
        "reimbursed_by_user_id": str(report.reimbursed_by_user_id) if report.reimbursed_by_user_id else None,
        "line_count": len(lines_out),
        "total_amount": format(total, "f"),
        "lines": lines_out,
    }


def _load_report(report_id: uuid.UUID) -> HrmsExpenseReport | None:
    return db.session.scalar(
        select(HrmsExpenseReport)
        .where(HrmsExpenseReport.id == report_id)
        .options(
            selectinload(HrmsExpenseReport.user),
            selectinload(HrmsExpenseReport.lines).selectinload(HrmsExpenseLine.project),
        )
    )


def _is_owner(cu: CurrentUser, report: HrmsExpenseReport) -> bool:
    return cu.user is not None and report.user_id == cu.user.id


def _can_view_report(cu: CurrentUser, report: HrmsExpenseReport) -> bool:
    if is_hr_admin(cu):
        return True
    if _is_owner(cu, report):
        return True
    if is_hr_manager(cu) and cu.user is not None and _is_team_report(cu, report):
        return True
    return False


def _is_team_report(cu: CurrentUser, report: HrmsExpenseReport) -> bool:
    if cu.user is None:
        return False
    prof = db.session.get(HrmsEmployeeProfile, report.user_id)
    return prof is not None and prof.manager_user_id == cu.user.id


def _require_draft(report: HrmsExpenseReport) -> None:
    if report.status not in (EXPENSE_STATUS_DRAFT, EXPENSE_STATUS_REJECTED):
        raise ExpenseError("only draft or rejected reports may be edited", 409)


def _validate_category(raw: str) -> str:
    cat = (raw or "").strip().lower()
    allowed = {c[0] for c in EXPENSE_CATEGORIES}
    if cat not in allowed:
        raise ExpenseError(f"category must be one of: {', '.join(sorted(allowed))}")
    return cat


def _validate_project(cu: CurrentUser, project_id: uuid.UUID) -> Project:
    proj = db.session.get(Project, project_id)
    if proj is None:
        raise ExpenseError("project not found", 404)
    if not user_can_access_project(cu, project_id):
        raise ExpenseError("no access to this project", 403)
    return proj


def list_categories() -> list[dict[str, str]]:
    return [{"code": c, "label": label} for c, label in EXPENSE_CATEGORIES]


def list_expense_projects(cu: CurrentUser) -> list[dict[str, Any]]:
    rows = db.session.scalars(
        select(Project).where(project_access_clause(cu)).order_by(Project.name.asc()).limit(500)
    ).all()
    return [{"id": str(p.id), "name": p.name, "number": p.number} for p in rows]


def list_reports(cu: CurrentUser, *, status: str | None = None) -> list[dict[str, Any]]:
    if cu.user is None:
        raise ExpenseError("authentication required", 401)
    stmt = select(HrmsExpenseReport).options(selectinload(HrmsExpenseReport.user))
    if is_hr_admin(cu):
        pass
    else:
        stmt = stmt.where(HrmsExpenseReport.user_id == cu.user.id)
    if status:
        st = status.strip().lower()
        if st not in EXPENSE_STATUSES:
            raise ExpenseError("invalid status filter")
        stmt = stmt.where(HrmsExpenseReport.status == st)
    rows = db.session.scalars(stmt.order_by(HrmsExpenseReport.updated_at.desc()).limit(200)).all()
    return [_serialize_report(r, include_lines=False) for r in rows]


def create_report(cu: CurrentUser, data: dict[str, Any]) -> dict[str, Any]:
    if cu.user is None:
        raise ExpenseError("authentication required", 401)
    title = str(data.get("title") or "").strip()
    if not title:
        raise ExpenseError("title is required")
    currency = str(data.get("currency") or "USD").strip().upper()[:8] or "USD"
    report = HrmsExpenseReport(user_id=cu.user.id, title=title[:255], currency=currency)
    db.session.add(report)
    db.session.flush()
    write_hrms_audit(
        actor_user_id=cu.user.id,
        action="hrms.expense.create",
        entity_type="hrms_expense_report",
        entity_id=report.id,
    )
    db.session.commit()
    return _serialize_report(_load_report(report.id) or report)


def get_report(cu: CurrentUser, report_id: uuid.UUID) -> dict[str, Any]:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _can_view_report(cu, report):
        raise ExpenseError("forbidden", 403)
    return _serialize_report(report)


def update_report(cu: CurrentUser, report_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    _require_draft(report)
    if "title" in data:
        title = str(data.get("title") or "").strip()
        if not title:
            raise ExpenseError("title is required")
        report.title = title[:255]
    if "currency" in data and data.get("currency"):
        report.currency = str(data.get("currency")).strip().upper()[:8]
    if report.status == EXPENSE_STATUS_REJECTED:
        report.status = EXPENSE_STATUS_DRAFT
        report.rejection_reason = None
        report.approver_user_id = None
        report.decided_at = None
    db.session.commit()
    return _serialize_report(_load_report(report_id) or report)


def delete_report(cu: CurrentUser, report_id: uuid.UUID) -> None:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    if report.status not in (EXPENSE_STATUS_DRAFT, EXPENSE_STATUS_REJECTED):
        raise ExpenseError("only draft or rejected reports may be deleted", 409)
    for line in report.lines or []:
        _delete_line_receipt(line)
    db.session.delete(report)
    write_hrms_audit(
        actor_user_id=cu.user.id if cu.user else None,
        action="hrms.expense.delete",
        entity_type="hrms_expense_report",
        entity_id=report_id,
    )
    db.session.commit()


def add_line(cu: CurrentUser, report_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    _require_draft(report)
    project_id = _parse_uuid(data.get("project_id"))
    if project_id is None:
        raise ExpenseError("project_id is required")
    _validate_project(cu, project_id)
    spent_at = _parse_date(data.get("spent_at"))
    if spent_at is None:
        raise ExpenseError("spent_at is required (YYYY-MM-DD)")
    amount = _parse_amount(data.get("amount"))
    if amount is None:
        raise ExpenseError("amount must be a positive number")
    category = _validate_category(str(data.get("category") or ""))
    merchant = str(data.get("merchant") or "").strip()[:255] or None
    description = str(data.get("description") or "").strip()[:500] or None
    currency = str(data.get("currency") or report.currency).strip().upper()[:8] or report.currency
    line = HrmsExpenseLine(
        report_id=report.id,
        project_id=project_id,
        spent_at=spent_at,
        amount=amount,
        currency=currency,
        category=category,
        merchant=merchant,
        description=description,
    )
    db.session.add(line)
    db.session.commit()
    return _serialize_line(line, report_id=report.id)


def update_line(cu: CurrentUser, report_id: uuid.UUID, line_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    _require_draft(report)
    line = db.session.scalar(
        select(HrmsExpenseLine).where(HrmsExpenseLine.id == line_id, HrmsExpenseLine.report_id == report_id)
    )
    if line is None:
        raise ExpenseError("expense line not found", 404)
    if "project_id" in data:
        project_id = _parse_uuid(data.get("project_id"))
        if project_id is None:
            raise ExpenseError("project_id is required")
        _validate_project(cu, project_id)
        line.project_id = project_id
    if "spent_at" in data:
        spent_at = _parse_date(data.get("spent_at"))
        if spent_at is None:
            raise ExpenseError("spent_at must be YYYY-MM-DD")
        line.spent_at = spent_at
    if "amount" in data:
        amount = _parse_amount(data.get("amount"))
        if amount is None:
            raise ExpenseError("amount must be a positive number")
        line.amount = amount
    if "category" in data:
        line.category = _validate_category(str(data.get("category") or ""))
    if "merchant" in data:
        line.merchant = str(data.get("merchant") or "").strip()[:255] or None
    if "description" in data:
        line.description = str(data.get("description") or "").strip()[:500] or None
    if "currency" in data and data.get("currency"):
        line.currency = str(data.get("currency")).strip().upper()[:8]
    db.session.commit()
    return _serialize_line(line, report_id=report_id)


def delete_line(cu: CurrentUser, report_id: uuid.UUID, line_id: uuid.UUID) -> None:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    _require_draft(report)
    line = db.session.scalar(
        select(HrmsExpenseLine).where(HrmsExpenseLine.id == line_id, HrmsExpenseLine.report_id == report_id)
    )
    if line is None:
        raise ExpenseError("expense line not found", 404)
    _delete_line_receipt(line)
    db.session.delete(line)
    db.session.commit()


def _delete_line_receipt(line: HrmsExpenseLine) -> None:
    if line.receipt_document_id is None:
        return
    doc = db.session.get(Document, line.receipt_document_id)
    if doc is not None:
        ext = _receipt_storage_ext(doc)
        if ext:
            delete_stored(UploadCategory.HR_EXPENSE_RECEIPT, f"{doc.id}{ext}")
        db.session.delete(doc)
    line.receipt_document_id = None


def upload_receipt(cu: CurrentUser, report_id: uuid.UUID, line_id: uuid.UUID) -> dict[str, Any]:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    _require_draft(report)
    line = db.session.scalar(
        select(HrmsExpenseLine).where(HrmsExpenseLine.id == line_id, HrmsExpenseLine.report_id == report_id)
    )
    if line is None:
        raise ExpenseError("expense line not found", 404)

    f = request.files.get("file")
    if f is None or not getattr(f, "filename", None):
        raise ExpenseError("missing file field (multipart form-data)")

    resolved = resolve_hire_doc_upload(f.filename, f.mimetype)
    if resolved is None:
        raise ExpenseError(f"unsupported file type; allowed: {', '.join(sorted(HR_HIRE_DOC_EXT))}")
    raw_name, ext = resolved

    cl = request.content_length
    if cl is not None and cl > REceipt_MAX_BYTES:
        raise ExpenseError("file too large (max 10MB)")

    if line.receipt_document_id is not None:
        _delete_line_receipt(line)

    doc = Document(
        project_id=line.project_id,
        document_type="photo",
        title=f"Expense receipt — {line.category}",
        original_filename=secure_filename(raw_name)[:500],
        mime_type=(f.mimetype or "").strip()[:120] or None,
        uploaded_by_user_id=cu.user.id if cu.user else None,
        tags={"receipt_ext": ext, "hrms_expense_line_id": str(line.id)},
    )
    db.session.add(doc)
    db.session.flush()

    obj_name = f"{doc.id}{ext}"
    try:
        sz = save_upload(UploadCategory.HR_EXPENSE_RECEIPT, obj_name, f)
    except Exception as exc:
        db.session.rollback()
        raise ExpenseError(f"could not save file: {exc}", 500) from exc

    if sz == 0 or sz > REceipt_MAX_BYTES:
        delete_stored(UploadCategory.HR_EXPENSE_RECEIPT, obj_name)
        db.session.rollback()
        raise ExpenseError("invalid upload size", 400)

    doc.file_size_bytes = sz
    doc.file_url = _receipt_file_url(report_id, line_id)
    line.receipt_document_id = doc.id
    db.session.commit()
    return _serialize_line(line, report_id=report_id)


def receipt_file_response(cu: CurrentUser, report_id: uuid.UUID, line_id: uuid.UUID) -> Response:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _can_view_report(cu, report):
        raise ExpenseError("forbidden", 403)
    line = db.session.scalar(
        select(HrmsExpenseLine).where(HrmsExpenseLine.id == line_id, HrmsExpenseLine.report_id == report_id)
    )
    if line is None or line.receipt_document_id is None:
        raise ExpenseError("receipt not found", 404)
    doc = db.session.get(Document, line.receipt_document_id)
    if doc is None:
        raise ExpenseError("receipt not found", 404)
    ext = _receipt_storage_ext(doc) or ".jpg"
    return send_stored_file(
        UploadCategory.HR_EXPENSE_RECEIPT,
        f"{doc.id}{ext}",
        download_name=doc.original_filename or f"receipt{ext}",
        mimetype=doc.mime_type,
    )


def submit_report(cu: CurrentUser, report_id: uuid.UUID) -> dict[str, Any]:
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if not _is_owner(cu, report):
        raise ExpenseError("forbidden", 403)
    _require_draft(report)
    lines = list(report.lines or [])
    if not lines:
        raise ExpenseError("add at least one expense line before submitting")
    for ln in lines:
        if ln.receipt_document_id is None:
            raise ExpenseError("each line must have a receipt before submitting")
        if not user_can_access_project(cu, ln.project_id):
            raise ExpenseError("invalid project on expense line", 400)
    now = utc_now()
    report.status = EXPENSE_STATUS_SUBMITTED
    report.submitted_at = now
    report.rejection_reason = None
    report.approver_user_id = None
    report.decided_at = None
    write_hrms_audit(
        actor_user_id=cu.user.id if cu.user else None,
        action="hrms.expense.submit",
        entity_type="hrms_expense_report",
        entity_id=report.id,
    )
    db.session.commit()
    return _serialize_report(_load_report(report_id) or report)


def list_approvals(cu: CurrentUser) -> list[dict[str, Any]]:
    if not is_hr_manager(cu):
        raise ExpenseError("forbidden", 403)
    stmt = (
        select(HrmsExpenseReport)
        .where(HrmsExpenseReport.status == EXPENSE_STATUS_SUBMITTED)
        .options(selectinload(HrmsExpenseReport.user))
    )
    if not is_hr_admin(cu) and cu.user is not None:
        team_ids = select(HrmsEmployeeProfile.user_id).where(HrmsEmployeeProfile.manager_user_id == cu.user.id)
        stmt = stmt.where(HrmsExpenseReport.user_id.in_(team_ids))
    rows = db.session.scalars(stmt.order_by(HrmsExpenseReport.submitted_at.asc().nullslast()).limit(200)).all()
    return [_serialize_report(r, include_lines=True) for r in rows]


def approve_report(cu: CurrentUser, report_id: uuid.UUID) -> dict[str, Any]:
    if not is_hr_manager(cu):
        raise ExpenseError("forbidden", 403)
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if report.status != EXPENSE_STATUS_SUBMITTED:
        raise ExpenseError("report is not awaiting approval", 409)
    if not is_hr_admin(cu) and cu.user is not None and not _is_team_report(cu, report):
        raise ExpenseError("forbidden", 403)
    now = utc_now()
    report.status = EXPENSE_STATUS_APPROVED
    report.approver_user_id = cu.user.id if cu.user else None
    report.decided_at = now
    write_hrms_audit(
        actor_user_id=cu.user.id if cu.user else None,
        action="hrms.expense.approve",
        entity_type="hrms_expense_report",
        entity_id=report.id,
    )
    db.session.commit()
    return _serialize_report(_load_report(report_id) or report)


def reject_report(cu: CurrentUser, report_id: uuid.UUID, data: dict[str, Any]) -> dict[str, Any]:
    if not is_hr_manager(cu):
        raise ExpenseError("forbidden", 403)
    reason = str(data.get("rejection_reason") or data.get("reason") or "").strip()
    if not reason:
        raise ExpenseError("rejection_reason is required")
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if report.status != EXPENSE_STATUS_SUBMITTED:
        raise ExpenseError("report is not awaiting approval", 409)
    if not is_hr_admin(cu) and cu.user is not None and not _is_team_report(cu, report):
        raise ExpenseError("forbidden", 403)
    now = utc_now()
    report.status = EXPENSE_STATUS_REJECTED
    report.rejection_reason = reason[:2000]
    report.approver_user_id = cu.user.id if cu.user else None
    report.decided_at = now
    write_hrms_audit(
        actor_user_id=cu.user.id if cu.user else None,
        action="hrms.expense.reject",
        entity_type="hrms_expense_report",
        entity_id=report.id,
        details={"reason": reason[:500]},
    )
    db.session.commit()
    return _serialize_report(_load_report(report_id) or report)


def list_reimbursements(cu: CurrentUser) -> list[dict[str, Any]]:
    if not is_hr_admin(cu):
        raise ExpenseError("forbidden", 403)
    rows = db.session.scalars(
        select(HrmsExpenseReport)
        .where(
            HrmsExpenseReport.status == EXPENSE_STATUS_APPROVED,
            HrmsExpenseReport.reimbursed_at.is_(None),
        )
        .options(selectinload(HrmsExpenseReport.user))
        .order_by(HrmsExpenseReport.decided_at.asc().nullslast())
        .limit(500)
    ).all()
    return [_serialize_report(r, include_lines=True) for r in rows]


def export_reimbursements_csv(cu: CurrentUser) -> tuple[str, str]:
    if not is_hr_admin(cu):
        raise ExpenseError("forbidden", 403)
    reports = db.session.scalars(
        select(HrmsExpenseReport)
        .where(
            HrmsExpenseReport.status == EXPENSE_STATUS_APPROVED,
            HrmsExpenseReport.reimbursed_at.is_(None),
        )
        .options(
            selectinload(HrmsExpenseReport.user),
            selectinload(HrmsExpenseReport.lines).selectinload(HrmsExpenseLine.project),
        )
        .order_by(HrmsExpenseReport.decided_at.asc().nullslast())
    ).all()
    batch_id = uuid.uuid4()
    now = utc_now()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "report_id",
            "employee_name",
            "employee_email",
            "report_title",
            "line_date",
            "project_number",
            "project_name",
            "category",
            "merchant",
            "description",
            "amount",
            "currency",
            "receipt_document_id",
            "approved_date",
            "approver_user_id",
        ]
    )
    for report in reports:
        owner = report.user
        for line in report.lines or []:
            proj = line.project
            writer.writerow(
                [
                    str(report.id),
                    _user_name(owner),
                    owner.email if owner else "",
                    report.title,
                    line.spent_at.isoformat(),
                    proj.number if proj else "",
                    proj.name if proj else "",
                    line.category,
                    line.merchant or "",
                    line.description or "",
                    format(line.amount, "f"),
                    line.currency,
                    str(line.receipt_document_id) if line.receipt_document_id else "",
                    report.decided_at.date().isoformat() if report.decided_at else "",
                    str(report.approver_user_id) if report.approver_user_id else "",
                ]
            )
        report.exported_at = now
        report.export_batch_id = batch_id
    write_hrms_audit(
        actor_user_id=cu.user.id if cu.user else None,
        action="hrms.expense.export",
        entity_type="hrms_expense_export",
        entity_id=batch_id,
        details={"report_count": len(reports)},
    )
    db.session.commit()
    filename = f"expense-reimbursements-{now.date().isoformat()}.csv"
    return buf.getvalue(), filename


def mark_reimbursed(cu: CurrentUser, report_id: uuid.UUID) -> dict[str, Any]:
    if not is_hr_admin(cu):
        raise ExpenseError("forbidden", 403)
    report = _load_report(report_id)
    if report is None:
        raise ExpenseError("expense report not found", 404)
    if report.status != EXPENSE_STATUS_APPROVED:
        raise ExpenseError("only approved reports may be marked reimbursed", 409)
    if report.reimbursed_at is not None:
        raise ExpenseError("report is already reimbursed", 409)
    now = utc_now()
    report.status = EXPENSE_STATUS_REIMBURSED
    report.reimbursed_at = now
    report.reimbursed_by_user_id = cu.user.id if cu.user else None
    write_hrms_audit(
        actor_user_id=cu.user.id if cu.user else None,
        action="hrms.expense.reimburse",
        entity_type="hrms_expense_report",
        entity_id=report.id,
    )
    db.session.commit()
    return _serialize_report(_load_report(report_id) or report)


def register_expense_routes(bp: Blueprint) -> None:
    from flask import jsonify

    def _handle(fn):
        try:
            return fn()
        except ExpenseError as exc:
            return _json_error(exc.message, exc.status)

    @bp.get("/expense-categories")
    def hrms_expense_categories():
        cu = current_user()
        if cu.user is None and not cu.is_dev_admin:
            return _json_error("authentication required", 401)
        return jsonify({"entity": "hrms_expense_categories", "items": list_categories()})

    @bp.get("/expense-projects")
    def hrms_expense_projects():
        cu = current_user()
        if cu.user is None and not cu.is_dev_admin:
            return _json_error("authentication required", 401)
        return jsonify({"entity": "hrms_expense_projects", "items": list_expense_projects(cu)})

    @bp.get("/expense-reports/approvals")
    def hrms_expense_approvals():
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_approvals", "items": list_approvals(cu)}))

    @bp.get("/expense-reports/reimbursements")
    def hrms_expense_reimbursements_list():
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_reimbursements", "items": list_reimbursements(cu)}))

    @bp.get("/expense-reports/export.csv")
    def hrms_expense_export_csv():
        cu = current_user()
        try:
            body, filename = export_reimbursements_csv(cu)
        except ExpenseError as exc:
            return _json_error(exc.message, exc.status)
        return Response(
            body,
            mimetype="text/csv",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @bp.get("/expense-reports")
    def hrms_expense_reports_list():
        cu = current_user()
        status = request.args.get("status")
        return _handle(lambda: jsonify({"entity": "hrms_expense_reports", "items": list_reports(cu, status=status)}))

    @bp.post("/expense-reports")
    def hrms_expense_reports_create():
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _json_error("JSON body required")
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": create_report(cu, data)}))

    @bp.get("/expense-reports/<uuid:report_id>")
    def hrms_expense_report_detail(report_id: uuid.UUID):
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": get_report(cu, report_id)}))

    @bp.patch("/expense-reports/<uuid:report_id>")
    def hrms_expense_report_patch(report_id: uuid.UUID):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _json_error("JSON body required")
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": update_report(cu, report_id, data)}))

    @bp.delete("/expense-reports/<uuid:report_id>")
    def hrms_expense_report_delete(report_id: uuid.UUID):
        cu = current_user()
        return _handle(
            lambda: (delete_report(cu, report_id), jsonify({"entity": "hrms_expense_report", "ok": True}))[1]
        )

    @bp.post("/expense-reports/<uuid:report_id>/submit")
    def hrms_expense_report_submit(report_id: uuid.UUID):
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": submit_report(cu, report_id)}))

    @bp.post("/expense-reports/<uuid:report_id>/approve")
    def hrms_expense_report_approve(report_id: uuid.UUID):
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": approve_report(cu, report_id)}))

    @bp.post("/expense-reports/<uuid:report_id>/reject")
    def hrms_expense_report_reject(report_id: uuid.UUID):
        cu = current_user()
        data = request.get_json(silent=True) or {}
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": reject_report(cu, report_id, data)}))

    @bp.post("/expense-reports/<uuid:report_id>/mark-reimbursed")
    def hrms_expense_report_mark_reimbursed(report_id: uuid.UUID):
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_report", "item": mark_reimbursed(cu, report_id)}))

    @bp.post("/expense-reports/<uuid:report_id>/lines")
    def hrms_expense_line_create(report_id: uuid.UUID):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _json_error("JSON body required")
        return _handle(lambda: jsonify({"entity": "hrms_expense_line", "item": add_line(cu, report_id, data)}))

    @bp.patch("/expense-reports/<uuid:report_id>/lines/<uuid:line_id>")
    def hrms_expense_line_patch(report_id: uuid.UUID, line_id: uuid.UUID):
        cu = current_user()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return _json_error("JSON body required")
        return _handle(lambda: jsonify({"entity": "hrms_expense_line", "item": update_line(cu, report_id, line_id, data)}))

    @bp.delete("/expense-reports/<uuid:report_id>/lines/<uuid:line_id>")
    def hrms_expense_line_delete(report_id: uuid.UUID, line_id: uuid.UUID):
        cu = current_user()
        return _handle(
            lambda: (delete_line(cu, report_id, line_id), jsonify({"entity": "hrms_expense_line", "ok": True}))[1]
        )

    @bp.post("/expense-reports/<uuid:report_id>/lines/<uuid:line_id>/receipt")
    def hrms_expense_line_receipt_upload(report_id: uuid.UUID, line_id: uuid.UUID):
        cu = current_user()
        return _handle(lambda: jsonify({"entity": "hrms_expense_line", "item": upload_receipt(cu, report_id, line_id)}))

    @bp.get("/expense-reports/<uuid:report_id>/lines/<uuid:line_id>/receipt/file")
    def hrms_expense_line_receipt_file(report_id: uuid.UUID, line_id: uuid.UUID):
        cu = current_user()
        try:
            return receipt_file_response(cu, report_id, line_id)
        except ExpenseError as exc:
            return _json_error(exc.message, exc.status)
