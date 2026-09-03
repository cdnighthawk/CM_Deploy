"""Bearer ingest API for the Autodesk Desktop Connector agent.

GET  /api/projects
POST /api/documents
POST /api/drawings
POST /api/drawings/<drawing_id>/file
"""
from __future__ import annotations

import hmac
from collections.abc import Iterable

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import Drawing
from ..services.drawing_upload import DrawingUploadError, replace_drawing_file
from ..services.ingest import (
    IngestError,
    as_uuid,
    handle_ingest_upload,
    list_ingest_projects,
    parse_ingest_metadata,
    serialize_ingest_doc,
)

bp = Blueprint("api_ingest", __name__)


def _configured_keys() -> list[str]:
    keys: list[str] = []
    for name in ("CM_API_KEY", "CM_INGEST_API_KEY"):
        raw = (current_app.config.get(name) or "").strip()
        if raw:
            keys.append(raw)
    return keys


def _tokens_equal(left: str, right: str) -> bool:
    a = left.encode("utf-8")
    b = right.encode("utf-8")
    if not a or len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def _matches_any(token: str, candidates: Iterable[str]) -> bool:
    return any(_tokens_equal(token, candidate) for candidate in candidates)


def _read_bearer() -> str:
    header = request.headers.get("Authorization") or ""
    prefix = "Bearer "
    if header.lower().startswith(prefix.lower()):
        return header[len(prefix) :].strip()
    return ""


def _require_ingest_auth():
    keys = _configured_keys()
    if not keys:
        return jsonify({"error": "ingest API key is not configured"}), 503
    token = _read_bearer()
    if not token:
        return jsonify({"error": "Authorization Bearer token required."}), 401
    if not _matches_any(token, keys):
        return jsonify({"error": "Invalid API key."}), 401
    return None


@bp.get("/api/projects")
def ingest_list_projects():
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    query = (
        request.args.get("q")
        or request.args.get("folder")
        or request.args.get("project_number")
        or ""
    )
    return jsonify({"projects": list_ingest_projects(query)})


@bp.post("/api/documents")
def ingest_upload_document():
    return _ingest_upload("document")


@bp.post("/api/drawings")
def ingest_upload_drawing():
    return _ingest_upload("drawing")


@bp.post("/api/drawings/<drawing_id>/file")
def ingest_replace_drawing_file(drawing_id: str):
    """Replace the stored PDF for an existing drawing (B2 backfill / re-upload)."""
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    did = as_uuid(drawing_id)
    if did is None:
        return jsonify({"error": "invalid drawing id"}), 400
    row = db.session.get(Drawing, did)
    if row is None:
        return jsonify({"error": "drawing not found"}), 404
    upload = request.files.get("file")
    if upload is None or not getattr(upload, "filename", None):
        return jsonify({"error": 'multipart uploads require a non-empty file field "file".'}), 400
    payload = upload.read()
    if not payload:
        return jsonify({"error": "multipart uploads require a non-empty file field."}), 400
    try:
        replace_drawing_file(row, payload)
        db.session.commit()
    except DrawingUploadError as exc:
        db.session.rollback()
        return jsonify({"error": exc.message}), exc.status
    except Exception:
        db.session.rollback()
        current_app.logger.exception("ingest drawing file replace failed")
        return jsonify({"error": "drawing file replace failed"}), 500
    item = serialize_ingest_doc(row, kind="drawing", project=None)
    return jsonify({"drawing": item, "replaced": True}), 200


def _ingest_upload(kind: str):
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    if not (request.content_type or "").lower().startswith("multipart/form-data"):
        return (
            jsonify(
                {
                    "error": 'multipart/form-data required with file field "file" and form field "metadata".',
                }
            ),
            400,
        )
    metadata = parse_ingest_metadata(request.form.get("metadata"))
    extra_hash = (request.form.get("content_hash") or "").strip()
    if extra_hash and not metadata.get("content_hash"):
        metadata["content_hash"] = extra_hash
    extra_source = (request.form.get("sourceSystem") or request.form.get("source") or "").strip()
    if extra_source and not metadata.get("source"):
        metadata["source"] = extra_source
    try:
        body, status = handle_ingest_upload(request.files.get("file"), metadata, kind=kind)
        db.session.commit()
    except DrawingUploadError as exc:
        if exc.drawing is not None:
            db.session.commit()
            return (
                jsonify(
                    {
                        "error": exc.message,
                        "drawing_id": str(exc.drawing.id),
                        "file_pending": True,
                    }
                ),
                exc.status,
            )
        db.session.rollback()
        row = _record_bearer_failure(metadata, kind, exc.message, exc.status, exc)
        payload = {"error": exc.message}
        if row is not None:
            payload["error_id"] = str(row.id)
        return jsonify(payload), exc.status
    except IngestError as exc:
        db.session.rollback()
        row = _record_bearer_failure(metadata, kind, exc.message, exc.status, exc)
        payload = {"error": exc.message}
        if row is not None:
            payload["error_id"] = str(row.id)
        return jsonify(payload), exc.status
    except Exception as exc:
        db.session.rollback()
        current_app.logger.exception("ingest %s upload failed", kind)
        reason = f"{type(exc).__name__}: {exc}"[:400]
        row = _record_bearer_failure(metadata, kind, f"{kind} upload failed: {reason}", 500, exc)
        payload = {"error": f"{kind} upload failed: {reason}"}
        if row is not None:
            payload["error_id"] = str(row.id)
        return jsonify(payload), 500
    return jsonify(body), status


def _record_bearer_failure(metadata: dict, kind: str, message: str, http_status: int, exc: Exception | None = None):
    from ..services import ingest_errors as ingest_err_svc

    row = ingest_err_svc.record_upload_failure(
        source="ingest_api",
        metadata=metadata,
        kind=kind,
        message=message,
        http_status=http_status,
        exc=exc,
    )
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return None
    return row
