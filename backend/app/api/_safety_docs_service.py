"""Company / project safety profiles and generated HTML packets."""
from __future__ import annotations

import copy
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from ..extensions import db
from ..models import CompanySafetyProfile, Project, ProjectSafetyPacket, ProjectSafetyProfile
from ..models.safety_profile import default_project_payload
from ..permissions.access import has_module_access
from ..safety_docs.context import missing_fields, overlay_project_identity
from ..safety_docs.packet import (
    COMPANY_DOCS,
    combine_company_html,
    combine_packet_html,
    render_company_docs,
    render_packet_docs,
)
from ..safety_docs.paths import seed_company_path
from ._perms import CurrentUser
from ._safety_service import SafetyApiError
from ._serializers import iso


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _is_safety_admin(cu: CurrentUser) -> bool:
    if cu.is_dev_admin:
        return True
    user = cu.user
    if user is not None and getattr(user, "is_superuser", False):
        return True
    if cu.has_role("admin", "superuser", "safety_manager"):
        return True
    return has_module_access(cu, "safety", "admin")


def _can_write_safety(cu: CurrentUser) -> bool:
    if _is_safety_admin(cu):
        return True
    return has_module_access(cu, "safety", "write")


def _require_safety_read(cu: CurrentUser) -> None:
    if cu.is_dev_admin:
        return
    if not has_module_access(cu, "safety", "read"):
        raise SafetyApiError("safety access required", 403)


def _require_safety_write(cu: CurrentUser) -> None:
    if not _can_write_safety(cu):
        raise SafetyApiError("safety write required", 403)


def _require_safety_admin(cu: CurrentUser) -> None:
    if not _is_safety_admin(cu):
        raise SafetyApiError("safety admin required", 403)


def _require_project(cu: CurrentUser, project_id: uuid.UUID) -> Project:
    from ..permissions.project_scope import user_can_access_project

    project = db.session.get(Project, project_id)
    if project is None or getattr(project, "deleted_at", None) is not None:
        raise SafetyApiError("project not found", 404)
    if not user_can_access_project(cu, project_id):
        raise SafetyApiError("project not found", 404)
    return project


def _deep_merge(base: dict[str, Any], overlay: Mapping[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(base)
    for key, value in overlay.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _strip_doc_html(docs: Mapping[str, Any]) -> dict[str, Any]:
    """List/meta payload without large HTML bodies."""
    out: dict[str, Any] = {}
    for slug, doc in docs.items():
        if not isinstance(doc, Mapping):
            continue
        out[slug] = {
            "slug": slug,
            "title": doc.get("title") or slug,
            "generated_at": doc.get("generated_at"),
        }
    return out


def _identity_public(project: Project) -> dict[str, Any]:
    return {
        "id": str(project.id),
        "name": project.name,
        "number": project.number,
        "address_line1": project.address_line1,
        "address_line2": project.address_line2,
        "city": project.city,
        "state": project.state,
        "postal_code": project.postal_code,
        "start_date": iso(project.start_date),
        "end_date": iso(project.substantial_completion_date),
    }


def _packet_public(row: ProjectSafetyPacket | None, *, include_html: bool = False) -> dict[str, Any] | None:
    if row is None:
        return None
    body: dict[str, Any] = {
        "id": str(row.id),
        "project_id": str(row.project_id),
        "version": row.version,
        "status": row.status,
        "missing_fields": list(row.missing_fields or []),
        "generated_at": iso(row.generated_at),
        "published_at": iso(row.published_at),
        "docs": _strip_doc_html(row.docs or {}),
    }
    if include_html:
        body["html"] = row.html or ""
    return body


def _company_public(row: CompanySafetyProfile) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "payload": row.payload or {},
        "template_version": row.template_version,
        "docs_version": row.docs_version,
        "docs_generated_at": iso(row.docs_generated_at),
        "docs": _strip_doc_html(row.docs or {}),
        "updated_at": iso(row.updated_at),
    }


def ensure_company_profile() -> CompanySafetyProfile:
    row = db.session.scalar(select(CompanySafetyProfile).order_by(CompanySafetyProfile.created_at.asc()).limit(1))
    if row is not None:
        return row
    seed_path = seed_company_path()
    payload = _load_json(seed_path) if seed_path.is_file() else {}
    row = CompanySafetyProfile(payload=payload, template_version=1, docs={}, docs_version=0)
    db.session.add(row)
    db.session.flush()
    return row


def get_company_profile(cu: CurrentUser) -> dict[str, Any]:
    _require_safety_read(cu)
    row = ensure_company_profile()
    db.session.commit()
    return {"entity": "company_safety_profile", "item": _company_public(row), "can_edit": _is_safety_admin(cu)}


def put_company_profile(data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    _require_safety_admin(cu)
    row = ensure_company_profile()
    incoming = data.get("payload") if isinstance(data.get("payload"), Mapping) else data
    if not isinstance(incoming, Mapping):
        raise SafetyApiError("payload object required", 400)
    row.payload = _deep_merge(dict(row.payload or {}), incoming)
    flag_modified(row, "payload")
    db.session.commit()
    return {"entity": "company_safety_profile", "item": _company_public(row), "can_edit": True}


def regenerate_company_docs(cu: CurrentUser) -> dict[str, Any]:
    _require_safety_admin(cu)
    row = ensure_company_profile()
    rendered = render_company_docs(row.payload or {}, version=row.docs_version + 1)
    stored: dict[str, Any] = {}
    now = _now()
    for slug, doc in rendered.items():
        stored[slug] = {
            "slug": slug,
            "title": doc["title"],
            "markdown": doc["markdown"],
            "html": combine_company_html(doc, title=doc["title"]),
            "generated_at": now.isoformat(),
        }
    row.docs = stored
    row.docs_version = int(row.docs_version or 0) + 1
    row.docs_generated_at = now
    flag_modified(row, "docs")
    db.session.commit()
    return {"entity": "company_safety_profile", "item": _company_public(row), "can_edit": True}


def list_company_docs(cu: CurrentUser) -> dict[str, Any]:
    _require_safety_read(cu)
    row = ensure_company_profile()
    if not row.docs:
        rendered = render_company_docs(row.payload or {}, version=max(row.docs_version, 1))
        now = _now()
        stored: dict[str, Any] = {}
        for slug, doc in rendered.items():
            stored[slug] = {
                "slug": slug,
                "title": doc["title"],
                "markdown": doc["markdown"],
                "html": combine_company_html(doc, title=doc["title"]),
                "generated_at": now.isoformat(),
            }
        row.docs = stored
        if not row.docs_version:
            row.docs_version = 1
        row.docs_generated_at = now
        flag_modified(row, "docs")
        db.session.commit()
    items = []
    for slug, title, _rel in COMPANY_DOCS:
        doc = (row.docs or {}).get(slug) or {}
        items.append(
            {
                "slug": slug,
                "title": doc.get("title") or title,
                "generated_at": doc.get("generated_at"),
            }
        )
    return {
        "entity": "company_safety_docs",
        "items": items,
        "docs_version": row.docs_version,
        "can_edit": _is_safety_admin(cu),
    }


def get_company_doc(slug: str, cu: CurrentUser) -> dict[str, Any]:
    _require_safety_read(cu)
    row = ensure_company_profile()
    if not row.docs:
        list_company_docs(cu)
        row = ensure_company_profile()
    key = (slug or "").strip().lower()
    doc = (row.docs or {}).get(key)
    if not isinstance(doc, Mapping):
        raise SafetyApiError("company document not found", 404)
    return {
        "entity": "company_safety_doc",
        "item": {
            "slug": key,
            "title": doc.get("title") or key,
            "html": doc.get("html") or "",
            "markdown": doc.get("markdown") or "",
            "generated_at": doc.get("generated_at"),
            "docs_version": row.docs_version,
        },
    }


def _ensure_project_profile(project: Project) -> ProjectSafetyProfile:
    row = db.session.scalar(
        select(ProjectSafetyProfile).where(ProjectSafetyProfile.project_id == project.id)
    )
    if row is not None:
        return row
    payload = overlay_project_identity(default_project_payload(), project)
    row = ProjectSafetyProfile(project_id=project.id, payload=payload)
    db.session.add(row)
    db.session.flush()
    return row


def _merged_payload(project: Project, profile: ProjectSafetyProfile) -> dict[str, Any]:
    return overlay_project_identity(profile.payload or {}, project)


def get_project_profile(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_safety_read(cu)
    project = _require_project(cu, project_id)
    profile = _ensure_project_profile(project)
    payload = _merged_payload(project, profile)
    packet = db.session.scalar(select(ProjectSafetyPacket).where(ProjectSafetyPacket.project_id == project.id))
    db.session.commit()
    return {
        "entity": "project_safety_profile",
        "item": {
            "project_id": str(project.id),
            "payload": payload,
            "identity": _identity_public(project),
            "missing_fields": missing_fields(payload),
            "packet": _packet_public(packet),
        },
        "can_edit": _can_write_safety(cu),
        "can_publish": _is_safety_admin(cu),
    }


def put_project_profile(project_id: uuid.UUID, data: Mapping[str, Any], cu: CurrentUser) -> dict[str, Any]:
    _require_safety_write(cu)
    project = _require_project(cu, project_id)
    profile = _ensure_project_profile(project)
    incoming = data.get("payload") if isinstance(data.get("payload"), Mapping) else data
    if not isinstance(incoming, Mapping):
        raise SafetyApiError("payload object required", 400)
    merged = _deep_merge(dict(profile.payload or default_project_payload()), incoming)
    profile.payload = overlay_project_identity(merged, project)
    flag_modified(profile, "payload")
    db.session.commit()
    return get_project_profile(project_id, cu)


def _store_packet(project: Project, profile: ProjectSafetyProfile, *, keep_published: bool) -> ProjectSafetyPacket:
    company = ensure_company_profile()
    payload = _merged_payload(project, profile)
    miss = missing_fields(payload)
    packet = db.session.scalar(select(ProjectSafetyPacket).where(ProjectSafetyPacket.project_id == project.id))
    next_version = (packet.version + 1) if packet is not None else 1
    rendered = render_packet_docs(company.payload or {}, payload, version=next_version)
    now = _now()
    stored_docs = {
        slug: {
            "slug": slug,
            "title": doc["title"],
            "markdown": doc["markdown"],
            "html": doc["html"],
        }
        for slug, doc in rendered.items()
    }
    title = f"{payload.get('projectName') or project.name} — Safety packet"
    html = combine_packet_html(stored_docs, draft=bool(miss), title=title)
    snapshot = {"company": company.payload or {}, "project": payload, "missing_fields": miss}
    status = "draft"
    published_at = None
    if keep_published and packet is not None and packet.status == "published" and not miss:
        status = "published"
        published_at = packet.published_at or now
    if packet is None:
        packet = ProjectSafetyPacket(project_id=project.id)
        db.session.add(packet)
    packet.version = next_version
    packet.status = status
    packet.json_snapshot = snapshot
    packet.html = html
    packet.docs = stored_docs
    packet.missing_fields = miss
    packet.generated_at = now
    packet.published_at = published_at
    flag_modified(packet, "json_snapshot")
    flag_modified(packet, "docs")
    flag_modified(packet, "missing_fields")
    db.session.flush()
    return packet


def regenerate_packet(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_safety_write(cu)
    project = _require_project(cu, project_id)
    profile = _ensure_project_profile(project)
    packet = _store_packet(project, profile, keep_published=True)
    db.session.commit()
    return {
        "entity": "project_safety_packet",
        "item": _packet_public(packet),
        "can_publish": _is_safety_admin(cu) and not (packet.missing_fields or []),
    }


def get_packet(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_safety_read(cu)
    project = _require_project(cu, project_id)
    packet = db.session.scalar(select(ProjectSafetyPacket).where(ProjectSafetyPacket.project_id == project.id))
    if packet is None:
        raise SafetyApiError("safety packet not generated", 404)
    if packet.status != "published" and not _can_write_safety(cu):
        raise SafetyApiError("safety packet not generated", 404)
    return {"entity": "project_safety_packet", "item": _packet_public(packet)}


def get_packet_html(project_id: uuid.UUID, cu: CurrentUser) -> str:
    _require_safety_read(cu)
    project = _require_project(cu, project_id)
    packet = db.session.scalar(select(ProjectSafetyPacket).where(ProjectSafetyPacket.project_id == project.id))
    if packet is None or not packet.html:
        raise SafetyApiError("safety packet not generated", 404)
    if packet.status != "published" and not _can_write_safety(cu):
        raise SafetyApiError("safety packet not generated", 404)
    return packet.html


def publish_packet(project_id: uuid.UUID, cu: CurrentUser) -> dict[str, Any]:
    _require_safety_admin(cu)
    project = _require_project(cu, project_id)
    profile = _ensure_project_profile(project)
    packet = _store_packet(project, profile, keep_published=False)
    miss = list(packet.missing_fields or [])
    if miss:
        db.session.commit()
        raise SafetyApiError(
            "cannot publish: missing " + ", ".join(miss),
            400,
        )
    packet.status = "published"
    packet.published_at = _now()
    db.session.commit()
    return {"entity": "project_safety_packet", "item": _packet_public(packet)}
