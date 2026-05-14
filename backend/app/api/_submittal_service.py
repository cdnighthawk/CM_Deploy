"""Submittal service: CRUD, attachments, audit trail, PDF annotation payloads."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import Document, Drawing, Submittal, SubmittalAudit, SubmittalPdfAnnotation
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_dt, _parse_uuid

__all__ = [
    "ApiError",
    "list_submittals",
    "get_submittal_detail",
    "create_submittal",
    "patch_submittal",
    "add_submittal_attachment",
    "get_document_annotations",
    "put_document_annotations",
]


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _is_writer(cu: CurrentUser) -> bool:
    return _is_admin(cu) or cu.has_role("standard")


def _bic_matches_user(cu: CurrentUser, ball_in_court: str | None) -> bool:
    if cu.is_dev_admin:
        return True
    raw = (ball_in_court or "").strip()
    if not raw:
        return False
    if cu.user is None:
        return False
    u = cu.user
    email = (u.email or "").strip().lower()
    name = f"{u.first_name or ''} {u.last_name or ''}".strip().lower()
    key = raw.lower()
    return key == email or key == name


def _can_edit_submittal(cu: CurrentUser, s: Submittal) -> bool:
    return _is_admin(cu) or _bic_matches_user(cu, s.ball_in_court)


def _can_annotate_submittal(cu: CurrentUser, s: Submittal) -> bool:
    return _is_admin(cu) or _bic_matches_user(cu, s.ball_in_court)


def _can_view_submittal(cu: CurrentUser, s: Submittal) -> bool:
    return (
        _is_admin(cu)
        or _is_writer(cu)
        or cu.has_role("read_only", "readonly")
        or _bic_matches_user(cu, s.ball_in_court)
    )


def _submittal_snapshot(s: Submittal) -> dict[str, Any]:
    return {
        "title": s.title,
        "spec_section": s.spec_section,
        "submittal_type": s.submittal_type,
        "status": s.status,
        "ball_in_court": s.ball_in_court,
        "due_at": _iso(s.due_at),
        "revision": s.revision,
        "responsible_contractor": s.responsible_contractor,
        "submit_by_at": _iso(s.submit_by_at),
        "received_from": s.received_from,
        "received_at": _iso(s.received_at),
        "sent_at": _iso(s.sent_at),
        "returned_at": _iso(s.returned_at),
        "response": s.response,
        "approvers": s.approvers,
    }


def _append_audit(
    s: Submittal,
    action: str,
    summary: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    actor_user_id: uuid.UUID | None,
) -> None:
    row = SubmittalAudit(
        submittal_id=s.id,
        actor_user_id=actor_user_id,
        action=action,
        summary=summary,
        before_json=before,
        after_json=after,
    )
    db.session.add(row)


def _submittal_docs(s: Submittal) -> list[Document]:
    """All ``documents`` rows linked via ``submittal_id`` (base ``Document`` rows)."""
    return list(s.documents or [])


def _current_attachment(s: Submittal) -> dict[str, Any] | None:
    docs = _submittal_docs(s)
    if not docs:
        return None
    best = max(docs, key=lambda d: (d.version, d.updated_at or d.created_at))
    return {
        "id": str(best.id),
        "version": best.version,
        "file_url": best.file_url,
        "title": best.title,
        "mime_type": best.mime_type,
        "original_filename": best.original_filename,
        "updated_at": _iso(best.updated_at),
    }


def _document_public(d: Document) -> dict[str, Any]:
    return {
        "id": str(d.id),
        "version": d.version,
        "file_url": d.file_url,
        "title": d.title,
        "mime_type": d.mime_type,
        "original_filename": d.original_filename,
        "parent_document_id": str(d.parent_document_id) if d.parent_document_id else None,
        "updated_at": _iso(d.updated_at),
    }


def _submittal_public(s: Submittal) -> dict[str, Any]:
    return {
        "id": str(s.id),
        "project_id": str(s.project_id),
        "number": s.number,
        "title": s.title,
        "spec_section": s.spec_section,
        "submittal_type": s.submittal_type,
        "status": s.status,
        "ball_in_court": s.ball_in_court or "",
        "due_at": _iso(s.due_at),
        "revision": s.revision,
        "responsible_contractor": s.responsible_contractor,
        "submit_by_at": _iso(s.submit_by_at),
        "received_from": s.received_from,
        "received_at": _iso(s.received_at),
        "sent_at": _iso(s.sent_at),
        "returned_at": _iso(s.returned_at),
        "response": s.response,
        "approvers": s.approvers,
        "current_attachment": _current_attachment(s),
        "created_at": _iso(s.created_at),
        "updated_at": _iso(s.updated_at),
    }


def _audit_public(a: SubmittalAudit) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "created_at": _iso(a.created_at),
        "action": a.action,
        "summary": a.summary,
        "actor_user_id": str(a.actor_user_id) if a.actor_user_id else None,
        "before_json": a.before_json,
        "after_json": a.after_json,
    }


def _get_submittal_eager(sid: uuid.UUID) -> Submittal | None:
    stmt = (
        select(Submittal)
        .where(Submittal.id == sid)
        .options(selectinload(Submittal.documents), selectinload(Submittal.audit_entries))
    )
    return db.session.scalars(stmt).first()


def list_submittals(project_id: uuid.UUID) -> dict[str, Any]:
    rows = db.session.scalars(
        select(Submittal)
        .where(Submittal.project_id == project_id)
        .options(selectinload(Submittal.documents))
        .order_by(Submittal.number.asc(), Submittal.created_at.asc())
    ).all()
    return {"items": [_submittal_public(s) for s in rows], "entity": "submittals"}


def get_submittal_detail(sid: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    s = _get_submittal_eager(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_view_submittal(cu, s):
        raise ApiError("not allowed to view this submittal", 403)
    audits = sorted(s.audit_entries or [], key=lambda a: a.created_at or _utcnow(), reverse=True)
    docs = sorted(_submittal_docs(s), key=lambda d: (d.version, d.created_at), reverse=True)
    return {
        "item": _submittal_public(s),
        "attachments": [_document_public(d) for d in docs],
        "audit": [_audit_public(a) for a in audits],
        "permissions": {
            "can_edit": _can_edit_submittal(cu, s),
            "can_annotate": _can_annotate_submittal(cu, s),
        },
    }


def create_submittal(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    if not _is_writer(cu):
        raise ApiError("not allowed to create submittals", 403)
    title = str(data.get("title") or "").strip()
    if not title:
        raise ApiError("title is required", 400)
    nxt = db.session.scalar(
        select(func.coalesce(func.max(Submittal.number), 0)).where(Submittal.project_id == project_id)
    )
    num = int(nxt or 0) + 1
    s = Submittal(
        project_id=project_id,
        number=num,
        title=title[:500],
        spec_section=(str(data.get("spec_section")).strip()[:120] or None) if data.get("spec_section") else None,
        submittal_type=(str(data.get("submittal_type")).strip()[:120] or None) if data.get("submittal_type") else None,
        status=str(data.get("status") or "draft").strip()[:40] or "draft",
        ball_in_court=(str(data.get("ball_in_court")).strip()[:200] or None) if data.get("ball_in_court") else None,
        due_at=_parse_dt(data.get("due_at")),
        revision=(str(data.get("revision")).strip()[:50] or None) if data.get("revision") else None,
        responsible_contractor=(str(data.get("responsible_contractor")).strip()[:300] or None)
        if data.get("responsible_contractor")
        else None,
        submit_by_at=_parse_dt(data.get("submit_by_at")),
        received_from=(str(data.get("received_from")).strip()[:300] or None) if data.get("received_from") else None,
        received_at=_parse_dt(data.get("received_at")),
        sent_at=_parse_dt(data.get("sent_at")),
        returned_at=_parse_dt(data.get("returned_at")),
        response=(str(data.get("response")).strip() or None) if data.get("response") is not None else None,
        approvers=data.get("approvers") if isinstance(data.get("approvers"), (list, dict)) else None,
    )
    db.session.add(s)
    db.session.flush()
    _append_audit(
        s,
        "create",
        f"Created submittal #{s.number}",
        None,
        _submittal_snapshot(s),
        cu.id,
    )
    db.session.commit()
    s2 = _get_submittal_eager(s.id)
    assert s2 is not None
    return get_submittal_detail(s2.id, cu)


def patch_submittal(sid: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _get_submittal_eager(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_edit_submittal(cu, s):
        raise ApiError("not allowed to edit this submittal", 403)
    before = _submittal_snapshot(s)
    if "title" in data:
        t = str(data.get("title") or "").strip()
        if not t:
            raise ApiError("title cannot be empty", 400)
        s.title = t[:500]
    if "spec_section" in data:
        v = data.get("spec_section")
        s.spec_section = (str(v).strip()[:120] or None) if v not in (None, "") else None
    if "submittal_type" in data:
        v = data.get("submittal_type")
        s.submittal_type = (str(v).strip()[:120] or None) if v not in (None, "") else None
    if "status" in data and data.get("status") is not None:
        s.status = str(data.get("status")).strip()[:40] or s.status
    if "ball_in_court" in data:
        v = data.get("ball_in_court")
        s.ball_in_court = (str(v).strip()[:200] or None) if v not in (None, "") else None
    if "due_at" in data:
        s.due_at = _parse_dt(data.get("due_at"))
    if "revision" in data:
        v = data.get("revision")
        s.revision = (str(v).strip()[:50] or None) if v not in (None, "") else None
    if "responsible_contractor" in data:
        v = data.get("responsible_contractor")
        s.responsible_contractor = (str(v).strip()[:300] or None) if v not in (None, "") else None
    if "submit_by_at" in data:
        s.submit_by_at = _parse_dt(data.get("submit_by_at"))
    if "received_from" in data:
        v = data.get("received_from")
        s.received_from = (str(v).strip()[:300] or None) if v not in (None, "") else None
    if "received_at" in data:
        s.received_at = _parse_dt(data.get("received_at"))
    if "sent_at" in data:
        s.sent_at = _parse_dt(data.get("sent_at"))
    if "returned_at" in data:
        s.returned_at = _parse_dt(data.get("returned_at"))
    if "response" in data:
        v = data.get("response")
        s.response = (str(v).strip() or None) if v not in (None, "") else None
    if "approvers" in data:
        ap = data.get("approvers")
        s.approvers = ap if isinstance(ap, (list, dict)) else None
    after = _submittal_snapshot(s)
    if after != before:
        _append_audit(s, "edit", "Updated submittal fields", before, after, cu.id)
    db.session.commit()
    s2 = _get_submittal_eager(sid)
    assert s2 is not None
    return get_submittal_detail(s2.id, cu)


def add_submittal_attachment(sid: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    s = _get_submittal_eager(sid)
    if s is None:
        raise ApiError("submittal not found", 404)
    if not _can_edit_submittal(cu, s):
        raise ApiError("not allowed to add attachments", 403)
    file_url = str(data.get("file_url") or "").strip()
    if not file_url:
        raise ApiError("file_url is required", 400)
    parent_id = _parse_uuid(data.get("parent_document_id"))
    version = 1
    if parent_id:
        parent = db.session.get(Document, parent_id)
        if parent is None or parent.submittal_id != s.id:
            raise ApiError("invalid parent_document_id", 400)
        version = int(parent.version or 1) + 1
    else:
        docs = _submittal_docs(s)
        if docs:
            version = max(d.version for d in docs) + 1

    title = (str(data.get("title")).strip()[:500] or None) if data.get("title") else None
    mime = (str(data.get("mime_type")).strip()[:120] or None) if data.get("mime_type") else None
    oname = (str(data.get("original_filename")).strip()[:500] or None) if data.get("original_filename") else None

    d = Document(
        project_id=s.project_id,
        document_type="other",
        title=title,
        file_url=file_url[:1024],
        mime_type=mime,
        original_filename=oname,
        version=version,
        parent_document_id=parent_id,
        submittal_id=s.id,
        uploaded_by_user_id=cu.id,
    )
    db.session.add(d)
    db.session.flush()
    _append_audit(
        s,
        "attachment_add",
        f"Added attachment v{version}",
        None,
        {"document_id": str(d.id), "version": version},
        cu.id,
    )
    db.session.commit()
    return {"item": _document_public(d), "entity": "submittal_attachment"}


def get_document_annotations(document_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    d = db.session.get(Document, document_id)
    if d is None or d.submittal_id is None or isinstance(d, Drawing):
        raise ApiError("document not found", 404)
    s = db.session.get(Submittal, d.submittal_id)
    if s is None:
        raise ApiError("document not found", 404)
    if not _can_view_submittal(cu, s):
        raise ApiError("not allowed to view this document", 403)
    row = db.session.scalar(
        select(SubmittalPdfAnnotation).where(SubmittalPdfAnnotation.document_id == document_id)
    )
    payload: Any = [] if row is None else row.payload_json
    if payload is None:
        payload = []
    return {
        "document_id": str(document_id),
        "submittal_id": str(s.id),
        "items": payload if isinstance(payload, list) else [],
        "permissions": {"can_annotate": _can_annotate_submittal(cu, s)},
    }


def put_document_annotations(document_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    d = db.session.get(Document, document_id)
    if d is None or d.submittal_id is None or isinstance(d, Drawing):
        raise ApiError("document not found", 404)
    s = db.session.get(Submittal, d.submittal_id)
    if s is None:
        raise ApiError("document not found", 404)
    if not _can_annotate_submittal(cu, s):
        raise ApiError("not allowed to annotate this attachment", 403)
    raw = data.get("items")
    if raw is None:
        raw = data.get("payload")
    if not isinstance(raw, list):
        raise ApiError("items must be a JSON array", 400)
    row = db.session.scalar(
        select(SubmittalPdfAnnotation).where(SubmittalPdfAnnotation.document_id == document_id)
    )
    if row is None:
        row = SubmittalPdfAnnotation(document_id=document_id, author_user_id=cu.id, payload_json=raw)
        db.session.add(row)
    else:
        row.payload_json = raw
        row.author_user_id = cu.id
    _append_audit(
        s,
        "annotation_save",
        f"Saved markups for document {document_id}",
        None,
        {"document_id": str(document_id), "markup_count": len(raw)},
        cu.id,
    )
    db.session.commit()
    return get_document_annotations(document_id, cu)
