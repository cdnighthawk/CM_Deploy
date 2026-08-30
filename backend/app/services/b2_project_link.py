"""Attach existing B2 objects to Project / Drawing rows without re-uploading."""
from __future__ import annotations

import json
import re
import uuid
from typing import Any

from sqlalchemy import func, select, text

from ..extensions import db
from ..models import Document, LeadEstimate, Project
from .object_storage import UploadCategory, b2_enabled
from .project_file_keys import safe_filename

_UUID_NAME = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}(?:\.[A-Za-z0-9]+)?$",
    re.I,
)
_JOB_NUM = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,31}$")


def parse_job_drawing_key(key: str, prefix: str = "") -> dict[str, str] | None:
    """Parse ``{prefix}/drawings/{job}/{discipline}/{set}/{filename}``."""
    rel = (key or "").replace("\\", "/").strip("/")
    pref = (prefix or "").strip().strip("/")
    if pref and rel.startswith(pref + "/"):
        rel = rel[len(pref) + 1 :]
    parts = [p for p in rel.split("/") if p]
    if len(parts) < 5 or parts[0] != UploadCategory.DRAWINGS.value:
        return None
    job, discipline, drawing_set, filename = parts[1], parts[2], parts[3], "/".join(parts[4:])
    if not filename or _UUID_NAME.match(job) or job.lower() in {"unassigned", "unknown"}:
        return None
    if not _JOB_NUM.match(job):
        return None
    object_name = "/".join(parts[1:])
    return {
        "job": job,
        "discipline": discipline,
        "drawing_set": drawing_set,
        "filename": filename,
        "object_name": object_name,
    }


def _project_id_for_number(number: str) -> uuid.UUID | None:
    """Lookup by number without selecting newer Project columns (local DBs may lag)."""
    row = db.session.execute(
        text(
            """
            SELECT id
            FROM projects
            WHERE deleted_at IS NULL
              AND lower(btrim(number)) = lower(:n)
            ORDER BY CASE status::text
                WHEN 'active' THEN 0
                WHEN 'complete' THEN 1
                WHEN 'planning' THEN 2
                ELSE 3
            END,
            updated_at DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"n": number},
    ).first()
    return row[0] if row else None


def _lead_project_id_for_number(number: str) -> uuid.UUID | None:
    row = db.session.execute(
        text(
            """
            SELECT project_id
            FROM lead_estimates
            WHERE project_id IS NOT NULL
              AND lower(btrim(number)) = lower(:n)
            ORDER BY updated_at DESC NULLS LAST
            LIMIT 1
            """
        ),
        {"n": number},
    ).first()
    return row[0] if row else None


def resolve_project_id_for_number(number: str, *, create_missing: bool = True) -> uuid.UUID | None:
    """Prefer the lead's job, then a project with this number, else create one."""
    key = (number or "").strip()
    if not key:
        raise ValueError("job number required")
    lead_pid = _lead_project_id_for_number(key)
    if lead_pid is not None:
        live = db.session.execute(
            text("SELECT id FROM projects WHERE id = :id AND deleted_at IS NULL"),
            {"id": lead_pid},
        ).first()
        if live is not None:
            return live[0]
    found_id = _project_id_for_number(key)
    if found_id is not None:
        return found_id
    if not create_missing:
        return None
    lead = db.session.scalar(
        select(LeadEstimate)
        .where(func.lower(func.trim(LeadEstimate.number)) == key.lower())
        .order_by(LeadEstimate.updated_at.desc().nullslast(), LeadEstimate.id.asc())
    )
    if lead is not None:
        from .lead_workspace import ensure_lead_workspace_project

        return ensure_lead_workspace_project(lead).id
    proj = Project(
        name=key,
        number=key[:50],
        status="active",
        project_type="commercial",
        notes="Created while linking Backblaze drawings to this job number.",
    )
    db.session.add(proj)
    db.session.flush()
    return proj.id


def _point_leads_at_linked_jobs(project_cache: dict[str, uuid.UUID]) -> int:
    """Point leads and estimates with the same job number at the linked project."""
    from ..models import Estimate
    from .lead_workspace import attach_lead_and_estimates

    attached = 0
    for number, pid in project_cache.items():
        leads = list(
            db.session.scalars(
                select(LeadEstimate).where(
                    func.lower(func.trim(LeadEstimate.number)) == number.lower()
                )
            ).all()
        )
        for lead in leads:
            attach_lead_and_estimates(lead, pid)
            for est in db.session.scalars(select(Estimate).where(Estimate.lead_estimate_id == lead.id)).all():
                est.project_id = pid
            attached += 1
    return attached


def repair_b2_sheet_numbers() -> dict[str, int]:
    """Fix sheet numbers on earlier B2 links that used a too-short filename parse."""
    rows = db.session.execute(
        text(
            """
            SELECT dr.id, d.original_filename, d.project_id
            FROM drawings dr
            JOIN documents d ON d.id = dr.id
            WHERE coalesce(d.tags->>'linked_from', '') = 'b2_key'
            """
        )
    ).fetchall()
    updated = 0
    by_key: dict[tuple[uuid.UUID, str], uuid.UUID] = {}
    for did, fname, pid in rows:
        sn = _sheet_number(fname or "") or ""
        db.session.execute(
            text("UPDATE drawings SET sheet_number = :sn WHERE id = :id"),
            {"sn": sn or None, "id": did},
        )
        updated += 1
        if pid and sn:
            key = (pid, sn)
            if key not in by_key:
                by_key[key] = did
            db.session.execute(
                text("UPDATE drawings SET drawing_series_id = :sid WHERE id = :id"),
                {"sid": by_key[key], "id": did},
            )
    return {"updated": updated, "series": len(by_key)}


def _existing_storage_objects(names: set[str]) -> set[str]:
    if not names:
        return set()
    rows = db.session.scalars(select(Document.tags).where(Document.tags.is_not(None))).all()
    found: set[str] = set()
    for tags in rows:
        if not isinstance(tags, dict):
            continue
        stored = str(tags.get("storage_object") or "").strip()
        if stored in names:
            found.add(stored)
    return found


def _sheet_number(filename: str) -> str | None:
    """Use the leading token (A1-001_BCK-1.pdf → A1-001) when it looks like a sheet id."""
    from .drawing_label import parse_filename

    return parse_filename(filename).get("sheet_number")


def _series_id_for_sheet(project_id: uuid.UUID, sheet_number: str | None) -> uuid.UUID | None:
    sn = (sheet_number or "").strip()
    if not sn:
        return None
    row = db.session.execute(
        text(
            """
            SELECT dr.drawing_series_id
            FROM drawings dr
            JOIN documents d ON d.id = dr.id
            WHERE d.project_id = :pid AND dr.sheet_number = :sn
            ORDER BY d.created_at ASC, dr.id ASC
            LIMIT 1
            """
        ),
        {"pid": project_id, "sn": sn},
    ).first()
    return row[0] if row else None


def _insert_linked_drawing(
    *,
    project_id: uuid.UUID,
    object_name: str,
    filename: str,
    title: str,
    sheet: str | None,
    discipline: str | None,
    drawing_set: str | None,
    size: int,
    series_id: uuid.UUID | None,
) -> uuid.UUID:
    did = uuid.uuid4()
    series = series_id or did
    url = f"/api/v1/drawings/{did}/file"
    db.session.execute(
        text(
            """
            INSERT INTO documents (
                id, project_id, document_type, title, original_filename, mime_type,
                file_size_bytes, file_url, tags, version, created_at, updated_at
            ) VALUES (
                :id, :pid, 'drawing', :title, :fname, 'application/pdf',
                :size, :url, CAST(:tags AS jsonb), 1, NOW(), NOW()
            )
            """
        ),
        {
            "id": did,
            "pid": project_id,
            "title": title,
            "fname": filename,
            "size": size or None,
            "url": url,
            "tags": json.dumps({"storage_object": object_name, "linked_from": "b2_key"}),
        },
    )
    db.session.execute(
        text(
            """
            INSERT INTO drawings (
                id, sheet_number, sheet_title, discipline, drawing_set, revision, drawing_series_id
            ) VALUES (
                :id, :sheet, :title, :disc, :dset, :rev, :series
            )
            """
        ),
        {
            "id": did,
            "sheet": (sheet[:50] if sheet else None),
            "title": title,
            "disc": (discipline[:50] if discipline else None),
            "dset": (drawing_set[:120] if drawing_set else None),
            "rev": (drawing_set[:50] if drawing_set else None),
            "series": series,
        },
    )
    return did


def _list_b2_objects() -> list[dict[str, Any]]:
    from flask import current_app

    from .object_storage import _s3_client

    bucket = (current_app.config.get("B2_BUCKET_NAME") or "").strip()
    prefix = (current_app.config.get("B2_PREFIX") or "").strip().strip("/")
    client = _s3_client()
    out: list[dict[str, Any]] = []
    kwargs: dict[str, Any] = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix + "/"
    for page in client.get_paginator("list_objects_v2").paginate(**kwargs):
        for obj in page.get("Contents") or []:
            key = obj.get("Key") or ""
            if not key or key.endswith("/"):
                continue
            out.append({"key": key, "size": int(obj.get("Size") or 0)})
    return out


def register_b2_job_files(
    *,
    objects: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
    create_missing: bool = True,
    job_numbers: set[str] | None = None,
) -> dict[str, Any]:
    """Create Drawing rows for B2 keys that already include a job number.

    Does not upload or download PDFs. UUID-only keys are counted and skipped.
    """
    from flask import current_app

    prefix = (current_app.config.get("B2_PREFIX") or "").strip().strip("/")
    if objects is None:
        if not b2_enabled():
            return {
                "entity": "b2_project_link",
                "scanned": 0,
                "created": 0,
                "already_linked": 0,
                "skipped_no_job": 0,
                "jobs": {},
                "error": "b2_disabled",
            }
        objects = _list_b2_objects()

    parsed_rows: list[tuple[dict[str, str], int]] = []
    skipped_no_job = 0
    for obj in objects:
        key = str(obj.get("key") or "")
        parsed = parse_job_drawing_key(key, prefix)
        if parsed is None:
            if "/drawings/" in f"/{key}/" or key.startswith("drawings/"):
                skipped_no_job += 1
            continue
        if job_numbers is not None and parsed["job"] not in job_numbers:
            continue
        parsed_rows.append((parsed, int(obj.get("size") or 0)))

    names = {p["object_name"] for p, _ in parsed_rows}
    already = _existing_storage_objects(names)
    created = 0
    jobs: dict[str, dict[str, int]] = {}
    project_cache: dict[str, uuid.UUID] = {}

    for parsed, size in parsed_rows:
        job = parsed["job"]
        slot = jobs.setdefault(job, {"created": 0, "already_linked": 0, "skipped_no_project": 0})
        if job not in project_cache:
            pid = resolve_project_id_for_number(job, create_missing=create_missing)
            if pid is None:
                slot["skipped_no_project"] += 1
                continue
            project_cache[job] = pid
        if parsed["object_name"] in already:
            slot["already_linked"] += 1
            continue
        if dry_run:
            slot["created"] += 1
            created += 1
            already.add(parsed["object_name"])
            continue
        fname = safe_filename(parsed["filename"], default="drawing.pdf")
        sheet = _sheet_number(fname)
        title = (fname.rsplit(".", 1)[0] if fname.lower().endswith(".pdf") else fname)[:500]
        series = _series_id_for_sheet(project_cache[job], sheet)
        _insert_linked_drawing(
            project_id=project_cache[job],
            object_name=parsed["object_name"],
            filename=fname[:500],
            title=title,
            sheet=sheet,
            discipline=parsed["discipline"],
            drawing_set=parsed["drawing_set"],
            size=size,
            series_id=series,
        )
        already.add(parsed["object_name"])
        slot["created"] += 1
        created += 1
        if created % 200 == 0:
            db.session.flush()

    attached = 0
    if not dry_run:
        attached = _point_leads_at_linked_jobs(project_cache)

    return {
        "entity": "b2_project_link",
        "scanned": len(objects),
        "created": created,
        "already_linked": sum(v["already_linked"] for v in jobs.values()),
        "skipped_no_job": skipped_no_job,
        "jobs": jobs,
        "leads_attached": attached,
        "dry_run": dry_run,
    }
