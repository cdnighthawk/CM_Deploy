"""Phase 1 correspondence archive: Graph mail → files under DOCUMENT_ROOT + register."""
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from flask import current_app, send_file
from sqlalchemy import or_, select
from werkzeug.utils import secure_filename

from ..extensions import db
from ..models import CorrespondenceItem, CorrespondenceSource, Project
from ._perms import CurrentUser
from ._rfi_service import ApiError, _parse_uuid

UNFILED = "_unfiled"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _is_admin(cu: CurrentUser) -> bool:
    return cu.is_dev_admin or cu.has_role("admin", "superuser")


def _can_view(cu: CurrentUser) -> bool:
    return _is_admin(cu) or cu.has_role("standard") or cu.has_role("readonly")


def _can_mutate(cu: CurrentUser) -> bool:
    return _is_admin(cu) or cu.has_role("standard")


def document_root() -> Path:
    raw = (os.environ.get("DOCUMENT_ROOT") or current_app.config.get("DOCUMENT_ROOT") or "").strip()
    if not raw:
        raw = (os.environ.get("DOCUMENT_UPLOAD_FOLDER") or current_app.config.get("DOCUMENT_UPLOAD_FOLDER") or "").strip()
    if raw:
        root = Path(raw).expanduser().resolve() / "correspondence"
    else:
        root = Path(current_app.instance_path).resolve() / "correspondence"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _plain_text(html_or_text: str) -> str:
    text = html_or_text or ""
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:20000]


def _serialize(item: CorrespondenceItem, project_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "projectId": str(item.project_id) if item.project_id else None,
        "projectName": project_name,
        "unfiled": item.project_id is None,
        "sourceType": item.source_type,
        "subject": item.subject,
        "fromName": item.from_name,
        "fromEmail": item.from_email,
        "sentAt": _iso(item.sent_at),
        "hasAttachments": bool(item.has_attachments),
        "attachmentCount": item.attachment_count,
        "storageRelpath": item.storage_relpath,
        "downloadUrl": f"/api/correspondence/{item.id}/download",
    }


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


def list_items(cu: CurrentUser, args: Mapping[str, Any]) -> dict[str, Any]:
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    stmt = select(CorrespondenceItem).order_by(CorrespondenceItem.sent_at.desc().nullslast())
    pid = _parse_uuid(args.get("project_id"))
    if pid:
        stmt = stmt.where(CorrespondenceItem.project_id == pid)
    elif str(args.get("unfiled") or "").strip() in ("1", "true", "yes"):
        stmt = stmt.where(CorrespondenceItem.project_id.is_(None))
    q = (args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                CorrespondenceItem.subject.ilike(like),
                CorrespondenceItem.from_email.ilike(like),
                CorrespondenceItem.from_name.ilike(like),
                CorrespondenceItem.search_text.ilike(like),
            )
        )
    rows = db.session.scalars(stmt.limit(500)).all()
    names: dict[uuid.UUID, str] = {}
    pids = {r.project_id for r in rows if r.project_id}
    if pids:
        for p in db.session.scalars(select(Project).where(Project.id.in_(pids))).all():
            names[p.id] = p.name
    return {
        "entity": "correspondence",
        "items": [_serialize(r, names.get(r.project_id) if r.project_id else None) for r in rows],
    }


def file_to_project(item_id: uuid.UUID, project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    item = db.session.get(CorrespondenceItem, item_id)
    if item is None:
        raise ApiError("correspondence item not found", 404)
    project = db.session.get(Project, project_id)
    if project is None or getattr(project, "deleted_at", None) is not None:
        raise ApiError("project not found", 404)
    item.project_id = project_id
    item.filed_by_user_id = cu.id
    item.filed_at = _utcnow()
    db.session.commit()
    return {"entity": "correspondence", "item": _serialize(item, project.name)}


def download_message(item_id: uuid.UUID, cu: CurrentUser):
    if not _can_view(cu):
        raise ApiError("forbidden", 403)
    item = db.session.get(CorrespondenceItem, item_id)
    if item is None:
        raise ApiError("correspondence item not found", 404)
    path = document_root() / item.storage_relpath / "message.txt"
    if not path.is_file():
        raise ApiError("file not on disk", 404)
    return send_file(path, as_attachment=True, download_name="message.txt", mimetype="text/plain")


def _write_message_files(rel: str, *, headers: str, body_text: str, attachments: list[tuple[str, bytes]]) -> int:
    folder = document_root() / rel
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "message.txt").write_text(headers + "\n\n" + body_text, encoding="utf-8")
    meta = {"files": ["message.txt"], "attachmentCount": len(attachments)}
    count = 0
    if attachments:
        att_dir = folder / "attachments"
        att_dir.mkdir(exist_ok=True)
        names = []
        for fname, payload in attachments:
            safe = secure_filename(fname) or f"file-{count + 1}"
            (att_dir / safe).write_bytes(payload)
            names.append(safe)
            count += 1
        meta["files"].extend([f"attachments/{n}" for n in names])
        meta["attachmentCount"] = count
    (folder / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return count


def _ensure_mailbox_source(mailbox: str) -> CorrespondenceSource:
    key = mailbox.strip().lower()
    src = db.session.scalar(
        select(CorrespondenceSource).where(
            CorrespondenceSource.source_type == "mailbox",
            CorrespondenceSource.external_key == key,
        )
    )
    if src is None:
        src = CorrespondenceSource(
            source_type="mailbox",
            external_key=key,
            display_name=mailbox,
            mailbox=mailbox,
            is_active=True,
        )
        db.session.add(src)
        db.session.flush()
    return src


def configured_mailboxes() -> list[str]:
    raw = (current_app.config.get("CORRESPONDENCE_MAILBOXES") or os.environ.get("CORRESPONDENCE_MAILBOXES") or "").strip()
    boxes = [b.strip() for b in raw.split(",") if b.strip()]
    if boxes:
        return boxes
    rows = db.session.scalars(
        select(CorrespondenceSource).where(
            CorrespondenceSource.source_type == "mailbox",
            CorrespondenceSource.is_active.is_(True),
        )
    ).all()
    return [r.mailbox or r.external_key for r in rows if (r.mailbox or r.external_key)]


def ingest_graph_message(detail: Mapping[str, Any], *, mailbox: str, source: CorrespondenceSource) -> CorrespondenceItem | None:
    mid = str(detail.get("id") or "").strip()
    if not mid:
        return None
    existing = db.session.scalar(select(CorrespondenceItem).where(CorrespondenceItem.graph_message_id == mid))
    if existing is not None:
        return existing
    frm = detail.get("from") if isinstance(detail.get("from"), Mapping) else {}
    from_email = str(frm.get("email") or frm.get("address") or "").strip() or None
    from_name = str(frm.get("name") or "").strip() or None
    if not from_email and isinstance(detail.get("from_email"), str):
        from_email = detail.get("from_email")
    if not from_name and isinstance(detail.get("from_name"), str):
        from_name = detail.get("from_name")
    subject = (str(detail.get("subject") or "").strip() or "(no subject)")[:500]
    sent_at = _parse_dt(detail.get("sentDateTime") or detail.get("receivedDateTime") or detail.get("sent_at"))
    body_raw = str(detail.get("body_content") or detail.get("bodyPreview") or "")
    body_text = _plain_text(body_raw)
    year = (sent_at or _utcnow()).year
    rel = f"{UNFILED}/{year}/{secure_filename(mid)[:80] or uuid.uuid4().hex}"
    attachments: list[tuple[str, bytes]] = []
    from ..api._notifications import download_mailbox_attachment

    for att in detail.get("attachments") or []:
        if not isinstance(att, Mapping):
            continue
        att_id = str(att.get("id") or "")
        if not att_id:
            continue
        try:
            data, fname, _ctype = download_mailbox_attachment(
                mailbox=mailbox, message_id=mid, attachment_id=att_id
            )
        except Exception:
            continue
        attachments.append((fname or "attachment", data))
    headers = "\n".join(
        [
            f"From: {from_name or ''} <{from_email or ''}>",
            f"Subject: {subject}",
            f"Date: {_iso(sent_at) or ''}",
            f"Mailbox: {mailbox}",
            f"Graph-Id: {mid}",
        ]
    )
    count = _write_message_files(rel, headers=headers, body_text=body_text, attachments=attachments)
    item = CorrespondenceItem(
        project_id=source.default_project_id,
        source_id=source.id,
        source_type="mailbox",
        graph_message_id=mid,
        subject=subject,
        from_name=from_name,
        from_email=from_email,
        sent_at=sent_at,
        storage_relpath=rel,
        search_text=f"{subject} {from_name or ''} {from_email or ''} {body_text}"[:20000],
        has_attachments=count > 0,
        attachment_count=count,
    )
    if source.default_project_id:
        item.filed_at = _utcnow()
    db.session.add(item)
    db.session.flush()
    return item


def sync_mailboxes(*, top: int = 40, cu: CurrentUser | None = None) -> dict[str, Any]:
    if cu and not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    from ..api._notifications import _graph_configured, get_mailbox_message, list_mailbox_messages

    if not _graph_configured():
        raise ApiError("Microsoft Graph is not configured", 409)
    mailboxes = configured_mailboxes()
    if not mailboxes:
        raise ApiError("No correspondence mailboxes configured", 409)
    created = 0
    skipped = 0
    errors: list[str] = []
    for mailbox in mailboxes:
        source = _ensure_mailbox_source(mailbox)
        try:
            listing = list_mailbox_messages(mailbox=mailbox, folder="inbox", top=top)
        except Exception as exc:
            errors.append(f"{mailbox}: {exc}")
            continue
        for summary in listing.get("items") or []:
            mid = str(summary.get("id") or "")
            if not mid:
                continue
            if db.session.scalar(select(CorrespondenceItem.id).where(CorrespondenceItem.graph_message_id == mid)):
                skipped += 1
                continue
            try:
                detail = get_mailbox_message(mailbox=mailbox, message_id=mid)
                before = db.session.scalar(
                    select(CorrespondenceItem.id).where(CorrespondenceItem.graph_message_id == mid)
                )
                ingest_graph_message(detail, mailbox=mailbox, source=source)
                after = db.session.scalar(
                    select(CorrespondenceItem.id).where(CorrespondenceItem.graph_message_id == mid)
                )
                if before is None and after is not None:
                    created += 1
            except Exception as exc:
                errors.append(f"{mailbox}/{mid[:12]}: {exc}")
    db.session.commit()
    return {
        "entity": "correspondence_sync",
        "mailboxes": mailboxes,
        "created": created,
        "skipped": skipped,
        "errors": errors[:20],
    }


def ingest_local_message(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    """Test/dev ingest without Graph — writes the same file layout."""
    if not _can_mutate(cu):
        raise ApiError("forbidden", 403)
    subject = (str(data.get("subject") or "").strip() or "(no subject)")[:500]
    body = _plain_text(str(data.get("body") or data.get("search_text") or ""))
    from_email = (str(data.get("from_email") or "").strip() or None)
    from_name = (str(data.get("from_name") or "").strip() or None)
    pid = _parse_uuid(data.get("project_id"))
    year = _utcnow().year
    rel = f"{UNFILED if pid is None else str(pid)}/{year}/{uuid.uuid4().hex[:16]}"
    headers = "\n".join(
        [
            f"From: {from_name or ''} <{from_email or ''}>",
            f"Subject: {subject}",
            f"Date: {_iso(_utcnow())}",
            "Source: local",
        ]
    )
    _write_message_files(rel, headers=headers, body_text=body, attachments=[])
    item = CorrespondenceItem(
        project_id=pid,
        source_type="upload",
        subject=subject,
        from_name=from_name,
        from_email=from_email,
        sent_at=_utcnow(),
        storage_relpath=rel,
        search_text=f"{subject} {from_name or ''} {from_email or ''} {body}"[:20000],
        has_attachments=False,
        attachment_count=0,
        filed_by_user_id=cu.id if pid else None,
        filed_at=_utcnow() if pid else None,
    )
    db.session.add(item)
    db.session.commit()
    project_name = None
    if pid:
        p = db.session.get(Project, pid)
        project_name = p.name if p else None
    return {"entity": "correspondence", "item": _serialize(item, project_name)}
