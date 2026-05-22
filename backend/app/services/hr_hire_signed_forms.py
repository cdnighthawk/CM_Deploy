"""Render and persist signed I-9 / W-4 hire wizard documents on employee profile."""
from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any

from flask import render_template
from sqlalchemy import select

from ..extensions import db
from ..models import Document, HrEmployeeDocument, HrHireApplication, User
from ..services.hr_i9_validate import _DOC_CATALOG_BY_LIST
from ..services.object_storage import UploadCategory, save_upload

_CITIZENSHIP_LABELS = {
    "citizen": "A citizen of the United States",
    "noncitizen_national": "A noncitizen national of the United States",
    "lawful_permanent_resident": "A lawful permanent resident (Alien Registration Number / USCIS Number)",
    "alien_authorized": "An alien authorized to work until (expiration date, if applicable)",
}

_FILING_STATUS_LABELS = {
    "single": "Single or Married filing separately",
    "married_joint": "Married filing jointly or Qualifying surviving spouse",
    "head_of_household": "Head of household",
}

_HR_DOC_CATEGORY = "Employment forms"
_I9_EMPLOYEE_DOC_TITLE = "Form I-9 Section 1 (signed)"
_W4_EMPLOYEE_DOC_TITLE = "Form W-4 (signed)"


def _fmt_dt(when: datetime | None) -> str:
    if when is None:
        return ""
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return when.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _employee_name(user: User | None, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    parts = [
        payload.get("first_name") or (user.first_name if user else None),
        payload.get("middle_initial"),
        payload.get("last_name") or (user.last_name if user else None),
    ]
    return " ".join(str(p).strip() for p in parts if p and str(p).strip())


def _doc_block_lines(block: dict[str, Any] | None) -> list[tuple[str, str]]:
    if not isinstance(block, dict):
        return []
    rows: list[tuple[str, str]] = []
    title = str(block.get("title") or "").strip()
    if title:
        rows.append(("Document title", title))
    authority = str(block.get("issuing_authority") or "").strip()
    if authority:
        rows.append(("Issuing authority", authority))
    number = str(block.get("number") or "").strip()
    if number:
        rows.append(("Document number", number))
    expiration = str(block.get("expiration") or "").strip()
    if expiration:
        rows.append(("Expiration date", expiration))
    return rows


def _i9_context(
    *,
    user: User,
    section1: dict[str, Any],
    signature_png: str,
    signed_at: datetime,
    typed_full_name: str,
) -> dict[str, Any]:
    status = section1.get("citizenship_status")
    doc_choice = section1.get("document_choice")
    identity_docs: list[tuple[str, str]] = []
    if doc_choice == "list_a":
        identity_docs.extend(_doc_block_lines(section1.get("list_a")))
    elif doc_choice == "list_b_c":
        identity_docs.append(("List B", ""))
        identity_docs.extend(_doc_block_lines(section1.get("list_b")))
        identity_docs.append(("List C", ""))
        identity_docs.extend(_doc_block_lines(section1.get("list_c")))

    return {
        "employee_name": _employee_name(user, section1),
        "employee_email": user.email,
        "signed_at": _fmt_dt(signed_at),
        "typed_full_name": typed_full_name,
        "signature_png": signature_png,
        "section1": section1,
        "citizenship_label": _CITIZENSHIP_LABELS.get(str(status or ""), str(status or "")),
        "document_choice_label": "List A document" if doc_choice == "list_a" else "List B and List C documents",
        "identity_docs": identity_docs,
    }


def _w4_context(
    *,
    user: User,
    w4: dict[str, Any],
    signature_png: str,
    signed_at: datetime,
    typed_full_name: str,
) -> dict[str, Any]:
    return {
        "employee_name": _employee_name(user, w4),
        "employee_email": user.email,
        "signed_at": _fmt_dt(signed_at),
        "typed_full_name": typed_full_name,
        "signature_png": signature_png,
        "w4": w4,
        "filing_status_label": _FILING_STATUS_LABELS.get(str(w4.get("filing_status") or ""), str(w4.get("filing_status") or "")),
    }


def render_signed_i9_html(
    *,
    user: User,
    section1: dict[str, Any],
    signature_png: str,
    signed_at: datetime,
    typed_full_name: str,
) -> str:
    return render_template(
        "documents/hire_i9_signed.html",
        **_i9_context(
            user=user,
            section1=section1,
            signature_png=signature_png,
            signed_at=signed_at,
            typed_full_name=typed_full_name,
        ),
    )


def render_signed_w4_html(
    *,
    user: User,
    w4: dict[str, Any],
    signature_png: str,
    signed_at: datetime,
    typed_full_name: str,
) -> str:
    return render_template(
        "documents/hire_w4_signed.html",
        **_w4_context(
            user=user,
            w4=w4,
            signature_png=signature_png,
            signed_at=signed_at,
            typed_full_name=typed_full_name,
        ),
    )


def render_i9_preview_html(
    *,
    user: User,
    section1: dict[str, Any],
    hire_row: HrHireApplication | None,
) -> str:
    signed = bool(hire_row and hire_row.i9_signed_at)
    status = section1.get("citizenship_status")
    doc_choice = section1.get("document_choice")
    identity_docs: list[tuple[str, str]] = []
    if doc_choice == "list_a":
        identity_docs.extend(_doc_block_lines(section1.get("list_a")))
    elif doc_choice == "list_b_c":
        identity_docs.append(("List B", ""))
        identity_docs.extend(_doc_block_lines(section1.get("list_b")))
        identity_docs.append(("List C", ""))
        identity_docs.extend(_doc_block_lines(section1.get("list_c")))

    return render_template(
        "documents/hire_i9_preview.html",
        employee_name=_employee_name(user, section1),
        employee_email=user.email,
        signed=signed,
        signed_at=_fmt_dt(hire_row.i9_signed_at) if signed and hire_row else "",
        typed_full_name=_employee_name(user, section1),
        signature_png=hire_row.i9_signature_png if signed and hire_row else "",
        section1=section1,
        citizenship_label=_CITIZENSHIP_LABELS.get(str(status or ""), str(status or "")),
        document_choice_label="List A document" if doc_choice == "list_a" else "List B and List C documents",
        identity_docs=identity_docs,
    )


def render_w4_preview_html(
    *,
    user: User,
    w4: dict[str, Any],
    hire_row: HrHireApplication | None,
) -> str:
    signed = bool(hire_row and hire_row.w4_signed_at)
    return render_template(
        "documents/hire_w4_preview.html",
        employee_name=_employee_name(user, w4),
        employee_email=user.email,
        signed=signed,
        signed_at=_fmt_dt(hire_row.w4_signed_at) if signed and hire_row else "",
        typed_full_name=_employee_name(user, w4),
        signature_png=hire_row.w4_signature_png if signed and hire_row else "",
        w4=w4,
        filing_status_label=_FILING_STATUS_LABELS.get(str(w4.get("filing_status") or ""), str(w4.get("filing_status") or "")),
    )


def _upsert_employee_document(*, user_id: uuid.UUID, title: str, document_id: uuid.UUID) -> None:
    row = db.session.scalar(
        select(HrEmployeeDocument).where(
            HrEmployeeDocument.user_id == user_id,
            HrEmployeeDocument.category == _HR_DOC_CATEGORY,
            HrEmployeeDocument.title == title,
        )
    )
    if row is None:
        row = HrEmployeeDocument(
            user_id=user_id,
            category=_HR_DOC_CATEGORY,
            title=title,
            sort_order=10 if "I-9" in title else 20,
            document_id=document_id,
        )
        db.session.add(row)
    else:
        row.document_id = document_id


def _persist_signed_html(
    *,
    hire_row: HrHireApplication,
    user: User,
    form_kind: str,
    html: str,
    existing_document_id: uuid.UUID | None,
    employee_doc_title: str,
    api_path: str,
) -> Document:
    category = UploadCategory.HR_I9 if form_kind == "i9" else UploadCategory.HR_W4
    doc = db.session.get(Document, existing_document_id) if existing_document_id else None
    if doc is None:
        doc = Document(
            document_type="other",
            title=employee_doc_title,
            uploaded_by_user_id=user.id,
            mime_type="text/html",
            original_filename=f"{form_kind}-signed.html",
        )
        db.session.add(doc)
        db.session.flush()

    payload = html.encode("utf-8")
    obj_name = f"{doc.id}.html"
    size = save_upload(category, obj_name, io.BytesIO(payload))
    doc.title = employee_doc_title
    doc.file_url = api_path
    doc.mime_type = "text/html"
    doc.original_filename = f"{form_kind}-signed.html"
    doc.file_size_bytes = size
    _upsert_employee_document(user_id=user.id, title=employee_doc_title, document_id=doc.id)
    return doc


def persist_signed_i9(
    *,
    hire_row: HrHireApplication,
    user: User,
    section1: dict[str, Any],
    signature_png: str,
    signed_at: datetime,
    typed_full_name: str,
    api_path: str,
) -> Document:
    html = render_signed_i9_html(
        user=user,
        section1=section1,
        signature_png=signature_png,
        signed_at=signed_at,
        typed_full_name=typed_full_name,
    )
    doc = _persist_signed_html(
        hire_row=hire_row,
        user=user,
        form_kind="i9",
        html=html,
        existing_document_id=hire_row.i9_signed_document_id,
        employee_doc_title=_I9_EMPLOYEE_DOC_TITLE,
        api_path=api_path,
    )
    hire_row.i9_signed_document_id = doc.id
    return doc


def persist_signed_w4(
    *,
    hire_row: HrHireApplication,
    user: User,
    w4: dict[str, Any],
    signature_png: str,
    signed_at: datetime,
    typed_full_name: str,
    api_path: str,
) -> Document:
    html = render_signed_w4_html(
        user=user,
        w4=w4,
        signature_png=signature_png,
        signed_at=signed_at,
        typed_full_name=typed_full_name,
    )
    doc = _persist_signed_html(
        hire_row=hire_row,
        user=user,
        form_kind="w4",
        html=html,
        existing_document_id=hire_row.w4_signed_document_id,
        employee_doc_title=_W4_EMPLOYEE_DOC_TITLE,
        api_path=api_path,
    )
    hire_row.w4_signed_document_id = doc.id
    return doc


def signed_form_staff_url(user_id: uuid.UUID, kind: str) -> str:
    return f"/api/v1/hr/applications/{user_id}/signed-forms/{kind}"


def signed_form_storage_name(document_id: uuid.UUID) -> str:
    return f"{document_id}.html"
