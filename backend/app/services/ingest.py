"""Autodesk Desktop Connector ingest: project match + file upload."""
from __future__ import annotations

import hashlib
import io
import json
import re
import uuid
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.orm import joinedload
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from ..api._lead_estimate_queries import _not_archived_or_declined, _not_grouped_child
from ..extensions import db
from ..models import Document, Drawing, LeadEstimate, Project
from .drawing_upload import _create_drawing_row
from .lead_workspace import attach_lead_and_estimates, ensure_lead_workspace_project
from .object_storage import StorageError, UploadCategory, save_upload
from .project_file_keys import preferred_document_object_name

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_DOCUMENT_TYPES = frozenset(
    {
        "drawing",
        "rfi",
        "submittal",
        "specification",
        "contract",
        "change_order",
        "invoice",
        "photo",
        "report",
        "ai_review_export",
        "safety_doc",
        "permit",
        "other",
    }
)
_MAX_BYTES = 52_428_800


class IngestError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def as_uuid(value: Any) -> uuid.UUID | None:
    raw = text(value)
    if not raw or not _UUID_RE.match(raw):
        return None
    return uuid.UUID(raw)


def text(value: Any) -> str:
    return str(value).strip() if isinstance(value, str) else ""


def folder_to_project_number(folder_name: str) -> str:
    raw = text(folder_name)
    if not raw:
        return ""
    proj = re.match(r"^PROJ[-_]?(\d{4})[-_](\d{1,6})$", raw, re.IGNORECASE)
    if proj:
        year = int(proj.group(1))
        seq = proj.group(2)
        return f"{year % 100:02d}{seq.zfill(4)}"
    digits = re.match(r"^(\d{6,})$", raw)
    if digits:
        return digits.group(1)
    return raw


def parse_ingest_metadata(raw: Any) -> dict[str, Any]:
    if raw is None or raw == "":
        return {}
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def lead_is_archived(lead: LeadEstimate) -> bool:
    """True when Bid Board would hide this row as archived or declined."""
    if lead.is_archived is True:
        return True
    bucket = (lead.workflow_bucket or "").upper()
    if "ARCHIVED" in bucket or "DECLINED" in bucket:
        return True
    state = (lead.submission_state or "").strip().lower().replace("_", "").replace("-", "")
    return state == "declined"


def serialize_project(
    *,
    project_id: uuid.UUID,
    kind: str,
    name: str | None,
    project_number: str | None,
    job_id: uuid.UUID | None,
    lead_estimate_id: uuid.UUID | None,
    archived: bool = False,
) -> dict[str, Any]:
    number = text(project_number)
    label = text(name)
    hints = [h for h in dict.fromkeys([number, label]) if h]
    return {
        "id": str(project_id),
        "project_id": str(project_id),
        "kind": kind,
        "name": label,
        "project_number": number or None,
        "job_id": str(job_id) if job_id else None,
        "lead_estimate_id": str(lead_estimate_id) if lead_estimate_id else None,
        "folder_hints": hints,
        "archived": bool(archived),
    }


def project_from_job(job: Project, lead: LeadEstimate | None = None) -> dict[str, Any]:
    archived = (job.status or "") == "archived" or (lead is not None and lead_is_archived(lead))
    return serialize_project(
        project_id=job.id,
        kind="job",
        name=job.name,
        project_number=job.number or (lead.number if lead else None),
        job_id=job.id,
        lead_estimate_id=lead.id if lead else None,
        archived=archived,
    )


def project_from_lead(lead: LeadEstimate) -> dict[str, Any]:
    job = lead.project
    if job is not None and job.deleted_at is None:
        return project_from_job(job, lead)
    return serialize_project(
        project_id=lead.id,
        kind="lead",
        name=lead.name,
        project_number=lead.number,
        job_id=lead.project_id,
        lead_estimate_id=lead.id,
        archived=lead_is_archived(lead),
    )


def project_matches_query(project: dict[str, Any], query: str) -> bool:
    q = text(query).lower()
    if not q:
        return True
    number_guess = folder_to_project_number(query).lower()
    haystack = [
        project.get("id"),
        project.get("project_id"),
        project.get("project_number"),
        project.get("name"),
        project.get("job_id"),
        project.get("lead_estimate_id"),
        *(project.get("folder_hints") or []),
    ]
    values = [str(v).lower() for v in haystack if v]
    return any(v == q or v == number_guess or q in v for v in values)


def list_ingest_projects(query: str = "") -> list[dict[str, Any]]:
    jobs = list(
        db.session.scalars(
            select(Project)
            .where(Project.deleted_at.is_(None))
            .order_by(Project.number.asc().nullslast(), Project.name.asc())
            .limit(500)
        ).all()
    )
    job_ids = [j.id for j in jobs]
    active_lead = and_(_not_archived_or_declined(), _not_grouped_child())
    leads_for_jobs: dict[uuid.UUID, LeadEstimate] = {}
    if job_ids:
        for lead in db.session.scalars(
            select(LeadEstimate)
            .where(LeadEstimate.project_id.in_(job_ids), active_lead)
            .order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.id.asc())
        ).all():
            if lead.project_id is not None and lead.project_id not in leads_for_jobs:
                leads_for_jobs[lead.project_id] = lead

    seen: set[str] = set()
    projects: list[dict[str, Any]] = []
    for job in jobs:
        item = project_from_job(job, leads_for_jobs.get(job.id))
        seen.add(item["id"])
        if item["lead_estimate_id"]:
            seen.add(item["lead_estimate_id"])
        projects.append(item)

    leads = list(
        db.session.scalars(
            select(LeadEstimate)
            .options(joinedload(LeadEstimate.project))
            .where(active_lead)
            .order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.name.asc())
            .limit(2000)
        ).unique()
        .all()
    )
    for lead in leads:
        if str(lead.id) in seen:
            continue
        if lead.project_id is not None and str(lead.project_id) in seen:
            continue
        item = project_from_lead(lead)
        if item["id"] in seen:
            continue
        seen.add(item["id"])
        projects.append(item)

    q = text(query)
    return [p for p in projects if project_matches_query(p, q)] if q else projects


def resolve_ingest_project(metadata: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    project_id = as_uuid(metadata.get("project_id") or metadata.get("projectId"))
    lead_estimate_id = as_uuid(metadata.get("lead_estimate_id") or metadata.get("leadEstimateId"))
    folder_name = text(
        metadata.get("folder_name") or metadata.get("folderName") or metadata.get("project_folder")
    )
    project_number = text(
        metadata.get("project_number")
        or metadata.get("projectNumber")
        or folder_to_project_number(folder_name)
    )

    if project_id:
        job = db.session.get(Project, project_id)
        if job is not None and job.deleted_at is None:
            lead = db.session.scalar(
                select(LeadEstimate)
                .where(LeadEstimate.project_id == job.id)
                .order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.id.asc())
            )
            return project_from_job(job, lead), "project_id"
        lead = db.session.get(LeadEstimate, project_id)
        if lead is not None:
            return project_from_lead(lead), "project_id"

    if lead_estimate_id:
        lead = db.session.get(LeadEstimate, lead_estimate_id)
        if lead is not None:
            return project_from_lead(lead), "lead_estimate_id"

    if project_number:
        job = db.session.scalar(
            select(Project).where(Project.deleted_at.is_(None), Project.number == project_number)
        )
        if job is not None:
            lead = db.session.scalar(
                select(LeadEstimate)
                .where(LeadEstimate.project_id == job.id)
                .order_by(LeadEstimate.bc_updated_at.desc().nullslast(), LeadEstimate.id.asc())
            )
            return project_from_job(job, lead), "project_number"
        lead = db.session.scalar(select(LeadEstimate).where(LeadEstimate.number == project_number))
        if lead is not None:
            return project_from_lead(lead), "project_number"

    name_query = folder_name or project_number
    if name_query:
        matches = list_ingest_projects(name_query)
        if len(matches) == 1:
            return matches[0], "folder_name"

    return None, None


def bind_ingest_workspace(project: dict[str, Any] | None) -> tuple[uuid.UUID | None, dict[str, Any] | None]:
    """Ensure a real Project row and return (job_id, refreshed ingest project).

    Desktop Connector often matches a lead that has no ``projects`` row yet.
    Drawings only store ``documents.project_id``, so we create the same planning
    workspace the website uses and attach the lead plus its estimates.
    """
    if not project:
        return None, None
    lead_id = as_uuid(project.get("lead_estimate_id"))
    if project.get("kind") == "job":
        job_id = as_uuid(project.get("job_id") or project.get("id"))
        if job_id and lead_id:
            lead = db.session.get(LeadEstimate, lead_id)
            if lead is not None:
                attach_lead_and_estimates(lead, job_id)
                return job_id, project_from_lead(lead)
        return job_id, project
    lead = db.session.get(LeadEstimate, as_uuid(project.get("id")) or lead_id)
    if lead is None:
        return as_uuid(project.get("job_id")), project
    workspace = ensure_lead_workspace_project(lead)
    return workspace.id, project_from_lead(lead)


def _folder_hint_from_path(raw: str) -> str:
    path = text(raw).replace("\\", "/").strip("/")
    if not path:
        return ""
    return path.split("/")[0]


def ingest_hints_from_document(doc: Document) -> dict[str, Any]:
    tags = _document_tags(doc)
    source_id = text(tags.get("source_id") or tags.get("sourceId") or tags.get("relative_path"))
    folder_name = text(tags.get("folder_name") or tags.get("folderName")) or _folder_hint_from_path(source_id)
    return {
        "project_id": tags.get("project_id") or tags.get("projectId"),
        "lead_estimate_id": tags.get("lead_estimate_id") or tags.get("leadEstimateId"),
        "project_number": tags.get("project_number") or tags.get("projectNumber"),
        "folder_name": folder_name,
    }


def relink_documents_for_lead(lead: LeadEstimate) -> int:
    """Attach unassigned docs already tagged with this lead to its workspace project."""
    if lead.project_id is None:
        return 0
    rows = list(
        db.session.scalars(
            select(Document).where(
                Document.project_id.is_(None),
                Document.tags.contains({"lead_estimate_id": str(lead.id)}),
            )
        ).all()
    )
    for doc in rows:
        doc.project_id = lead.project_id
    return len(rows)


def relink_unassigned_documents(*, limit: int = 2000) -> dict[str, Any]:
    """Attach B2 drawings/docs that have no ``project_id`` to a matched job."""
    rows = list(
        db.session.scalars(
            select(Document)
            .where(Document.project_id.is_(None))
            .order_by(Document.created_at.asc(), Document.id.asc())
            .limit(max(1, min(int(limit), 5000)))
        ).all()
    )
    linked: list[dict[str, Any]] = []
    leftover = 0
    for doc in rows:
        hints = ingest_hints_from_document(doc)
        lead_id = as_uuid(hints.get("lead_estimate_id"))
        project, matched_by = resolve_ingest_project(hints)
        if project is None and lead_id:
            lead = db.session.get(LeadEstimate, lead_id)
            if lead is not None:
                project, matched_by = project_from_lead(lead), "lead_estimate_id"
        job_id, project = bind_ingest_workspace(project)
        if job_id is None:
            leftover += 1
            continue
        doc.project_id = job_id
        tags = _document_tags(doc)
        if project and project.get("lead_estimate_id"):
            tags["lead_estimate_id"] = project["lead_estimate_id"]
        if project and project.get("project_number"):
            tags["project_number"] = project["project_number"]
        doc.tags = tags
        linked.append(
            {
                "id": str(doc.id),
                "documentType": doc.document_type,
                "projectId": str(job_id),
                "matchedBy": matched_by,
                "filename": doc.original_filename or doc.title,
            }
        )
    return {
        "entity": "drawing_relink",
        "scanned": len(rows),
        "linked": len(linked),
        "leftover": leftover,
        "items": linked,
    }


def _document_tags(doc: Document) -> dict[str, Any]:
    tags = doc.tags if isinstance(doc.tags, dict) else {}
    return dict(tags)


def find_by_content_hash(checksum: str, project_id: uuid.UUID | None) -> Document | None:
    q = select(Document).where(Document.tags.contains({"content_hash": checksum}))
    if project_id is not None:
        q = q.where(Document.project_id == project_id)
    q = q.order_by(Document.created_at.desc())
    return db.session.scalars(q).first()


def serialize_ingest_doc(doc: Document, *, kind: str, project: dict[str, Any] | None) -> dict[str, Any]:
    tags = _document_tags(doc)
    checksum = text(tags.get("content_hash"))
    created = doc.created_at.isoformat() if doc.created_at is not None else None
    return {
        "id": str(doc.id),
        "document_id": str(doc.id),
        "drawing_id": str(doc.id) if kind == "drawing" or isinstance(doc, Drawing) else None,
        "project_id": (
            (str(doc.project_id) if doc.project_id else None)
            or (project or {}).get("job_id")
            or ((project or {}).get("id") if (project or {}).get("kind") == "job" else None)
        ),
        "filename": doc.original_filename or doc.title,
        "mimeType": doc.mime_type,
        "sizeBytes": str(doc.file_size_bytes) if doc.file_size_bytes is not None else None,
        "content_hash": checksum or None,
        "checksumSha256": checksum or None,
        "source": text(tags.get("source")) or None,
        "sourceSystem": text(tags.get("source")) or None,
        "sourceId": text(tags.get("source_id")) or None,
        "lead_estimate_id": text(tags.get("lead_estimate_id")) or (project or {}).get("lead_estimate_id"),
        "file_url": doc.file_url,
        "createdAt": created,
    }


def handle_ingest_upload(file: FileStorage | None, metadata: dict[str, Any], *, kind: str) -> tuple[dict[str, Any], int]:
    if file is None or not getattr(file, "filename", None):
        raise IngestError('multipart uploads require a non-empty file field "file".')
    payload = file.read()
    if not payload:
        raise IngestError("multipart uploads require a non-empty file field.")
    if len(payload) > _MAX_BYTES:
        raise IngestError("file too large (max 50MB).")

    checksum = hashlib.sha256(payload).hexdigest()
    claimed = text(metadata.get("content_hash") or metadata.get("contentHash"))
    if claimed and claimed.lower() != checksum:
        raise IngestError("content_hash does not match the uploaded file.")

    project, matched_by = resolve_ingest_project(metadata)
    job_id, project = bind_ingest_workspace(project)
    if project and project.get("kind") == "job" and matched_by is None:
        matched_by = "workspace"

    existing = find_by_content_hash(checksum, job_id)
    if existing is not None:
        item = serialize_ingest_doc(existing, kind=kind, project=project)
        body: dict[str, Any] = {
            "document": item,
            "duplicate": True,
            "project": project,
            "matchedBy": matched_by,
        }
        if kind == "drawing":
            body["drawing"] = item
        return body, 200

    filename = (
        text(metadata.get("filename") or metadata.get("file_name"))
        or (file.filename or "").strip()
        or "upload"
    )
    filename = filename.replace("\\", "/").split("/")[-1][:500] or "upload"
    mime = (
        text(metadata.get("mimeType") or metadata.get("mime_type"))
        or (getattr(file, "mimetype", None) or "").strip()
        or ("application/pdf" if kind == "drawing" else "application/octet-stream")
    )
    if kind == "drawing" and "pdf" not in mime.lower() and not filename.lower().endswith(".pdf"):
        raise IngestError("POST /drawings requires a PDF.")

    source = (
        text(metadata.get("source") or metadata.get("sourceSystem"))
        or "autodesk_desktop_connector"
    )
    source_id = text(metadata.get("source_id") or metadata.get("sourceId") or metadata.get("relative_path")) or checksum
    tags = {
        "content_hash": checksum,
        "source": source,
        "source_id": source_id,
    }
    folder_name = text(
        metadata.get("folder_name") or metadata.get("folderName") or metadata.get("project_folder")
    )
    if folder_name:
        tags["folder_name"] = folder_name
    if project and project.get("lead_estimate_id"):
        tags["lead_estimate_id"] = project["lead_estimate_id"]
    if project and project.get("project_number"):
        tags["project_number"] = project["project_number"]
    if job_id:
        tags["project_id"] = str(job_id)

    if kind == "drawing":
        from .drawing_label import label_drawing, parse_folder_path

        rel = (
            text(metadata.get("relative_path") or metadata.get("relativePath") or metadata.get("source_path"))
            or filename
        )
        folder_labels = parse_folder_path(rel)
        labeled = label_drawing(
            filename=filename,
            folder_path=rel,
            sheet_number=text(metadata.get("sheet_number")) or None,
            sheet_title=text(metadata.get("sheet_title")) or None,
            discipline=text(metadata.get("discipline")) or folder_labels.get("discipline"),
            drawing_set=text(metadata.get("drawing_set")) or folder_labels.get("drawing_set"),
            revision=text(metadata.get("revision")) or None,
        )
        split_raw = metadata.get("split_pages")
        split_pages = str(split_raw).strip().lower() in ("1", "true", "yes", "on") if split_raw is not None else False
        created: list[Drawing] = []
        do_split = False
        reader = None
        page_count = 1
        if split_pages:
            try:
                from pypdf import PdfReader

                reader = PdfReader(io.BytesIO(payload))
                page_count = len(reader.pages)
            except Exception as exc:
                raise IngestError(f"invalid or unreadable PDF: {exc}") from exc
            if page_count < 1:
                raise IngestError("PDF has no pages.")
            do_split = page_count > 1
        if do_split:
            from .drawing_upload import _page_pdf_bytes

            for i in range(page_count):
                page_bytes = _page_pdf_bytes(reader, i)
                created.append(
                    _create_drawing_row(
                        project_id=job_id,
                        pdf_bytes=page_bytes,
                        raw_name=filename,
                        page_index=i,
                        page_count=page_count,
                        sheet_number=text(metadata.get("sheet_number")) or None,
                        sheet_title=labeled["sheet_title"],
                        discipline=labeled["discipline"],
                        drawing_set=labeled["drawing_set"],
                        revision=labeled["revision"] or "0",
                    )
                )
        else:
            created.append(
                _create_drawing_row(
                    project_id=job_id,
                    pdf_bytes=payload,
                    raw_name=filename,
                    page_index=None,
                    page_count=1,
                    sheet_number=labeled["sheet_number"],
                    sheet_title=labeled["sheet_title"],
                    discipline=labeled["discipline"],
                    drawing_set=labeled["drawing_set"],
                    revision=labeled["revision"] or "0",
                )
            )
        for row in created:
            row.tags = {**_document_tags(row), **tags}
        db.session.flush()
        first = created[0]
        item = serialize_ingest_doc(first, kind="drawing", project=project)
        body = {
            "document": item,
            "drawing": item,
            "project": project,
            "matchedBy": matched_by,
        }
        if len(created) > 1:
            body["items"] = [serialize_ingest_doc(d, kind="drawing", project=project) for d in created]
            body["split"] = True
            body["count"] = len(created)
        return body, 201

    raw_type = text(metadata.get("document_type") or metadata.get("documentType")).lower() or "other"
    dtype = raw_type if raw_type in _DOCUMENT_TYPES and raw_type != "drawing" else "other"
    safe = secure_filename(filename) or "upload"
    title = text(metadata.get("title")) or safe
    doc = Document(
        project_id=job_id,
        document_type=dtype,
        title=title[:500],
        original_filename=filename[:500],
        mime_type=mime[:120],
        file_size_bytes=len(payload),
        tags=tags,
    )
    db.session.add(doc)
    db.session.flush()
    object_name = preferred_document_object_name(doc)
    try:
        save_upload(UploadCategory.DOCUMENTS, object_name, io.BytesIO(payload))
    except StorageError as exc:
        raise IngestError(exc.message, exc.status) from exc
    doc.file_url = f"/api/v1/documents/{doc.id}/file"
    tags = {**tags, "storage_object": object_name}
    doc.tags = tags
    item = serialize_ingest_doc(doc, kind="document", project=project)
    return {
        "document": item,
        "project": project,
        "matchedBy": matched_by,
    }, 201
