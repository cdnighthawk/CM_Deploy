"""Bearer ingest API for the Autodesk Desktop Connector agent.

GET  /api/projects
GET  /api/ingest/estimates
GET  /api/estimates
POST /api/documents          JSON metadata only (bytes go to B2)
POST /api/drawings           JSON metadata only (bytes go to B2)
POST /api/drawings/<id>/b2-upload-url
POST /api/drawings/<id>/ack-file
POST /api/documents/<id>/b2-upload-url
POST /api/documents/<id>/ack-file
POST /api/ingest/events

Multipart file bodies are rejected (410). Desktop must mint a native B2 URL,
POST the PDF to Backblaze, then ack. See docs/DRAWING_FILE_STORE.md.
"""
from __future__ import annotations

import hmac
from collections.abc import Iterable

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import Document, Drawing
from ..services.drawing_upload import (
    DrawingUploadError,
    ack_document_file,
    ack_drawing_file,
    load_catalog_document,
    mint_unavailable_body,
    native_upload_hint_for_document,
    native_upload_hint_for_drawing,
    parse_ack_payload,
    persist_document_ack,
)
from ..services.ingest import (
    IngestError,
    agent_multipart_forbidden_body,
    as_uuid,
    handle_ingest_register,
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


@bp.post("/api/ingest/events")
def ingest_report_event():
    """Token-protected heartbeat from the Windows ACCDocs/Forma agent."""
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    from ..services.ingest_activity import record_agent_event

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return jsonify({"error": "JSON object required"}), 400
    try:
        item = record_agent_event(payload)
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 503
    except Exception:
        db.session.rollback()
        current_app.logger.exception("ingest event record failed")
        return jsonify({"error": "ingest event record failed"}), 500
    return jsonify({"item": item, "entity": "ingest_event"}), 201


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


def _parse_has_folder(raw: str | None) -> bool | None:
    value = (raw or "").strip().lower()
    if value in {"1", "true", "yes", "ready"}:
        return True
    if value in {"0", "false", "no"}:
        return False
    return None


@bp.get("/api/ingest/estimates")
@bp.get("/api/estimates")
def ingest_list_estimates():
    """Compact estimate → Y:\\Estimates folder map for the desktop ingest agent."""
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    from ..services.ingest_estimates import list_ingest_estimates

    query = (
        request.args.get("q")
        or request.args.get("folder")
        or request.args.get("project_key")
        or request.args.get("project_number")
        or ""
    )
    try:
        payload = list_ingest_estimates(
            query=query,
            project_id=request.args.get("project_id") or request.args.get("projectId"),
            folder_provision_status=request.args.get("folder_provision_status")
            or request.args.get("status"),
            has_folder=_parse_has_folder(request.args.get("has_folder")),
            due_from=request.args.get("due_from") or request.args.get("due_after"),
            due_to=request.args.get("due_to") or request.args.get("due_before"),
            limit=request.args.get("limit"),
            offset=request.args.get("offset"),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(payload)


@bp.post("/api/documents")
def ingest_upload_document():
    return _ingest_register("document")


@bp.post("/api/drawings")
def ingest_upload_drawing():
    return _ingest_register("drawing")


@bp.post("/api/drawings/<drawing_id>/file")
@bp.put("/api/drawings/<drawing_id>/content")
def ingest_replace_drawing_file(drawing_id: str):
    """Dead byte path. Desktop must mint + POST B2 + ack-file."""
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    return jsonify(agent_multipart_forbidden_body()), 410


@bp.post("/api/drawings/<drawing_id>/upload-session")
@bp.post("/api/drawings/<drawing_id>/b2-upload-url")
def ingest_drawing_mint(drawing_id: str):
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    did = as_uuid(drawing_id)
    if did is None:
        return jsonify({"error": "invalid drawing id"}), 400
    row = db.session.get(Drawing, did)
    if row is None:
        return jsonify({"error": "drawing not found"}), 404
    return _mint_response(row, kind="drawing")


@bp.post("/api/documents/<document_id>/upload-session")
@bp.post("/api/documents/<document_id>/b2-upload-url")
def ingest_document_mint(document_id: str):
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    did = as_uuid(document_id)
    if did is None:
        return jsonify({"error": "invalid document id"}), 400
    row = load_catalog_document(did)
    if row is None:
        return jsonify({"error": "document not found"}), 404
    if isinstance(row, Drawing):
        return _mint_response(row, kind="drawing")
    return _mint_response(row, kind="document")


@bp.post("/api/drawings/<drawing_id>/ack-file")
def ingest_ack_drawing(drawing_id: str):
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    did = as_uuid(drawing_id)
    if did is None:
        return jsonify({"error": "invalid drawing id"}), 400
    row = db.session.get(Drawing, did)
    if row is None:
        return jsonify({"error": "drawing not found"}), 404
    return _ack_row(row, kind="drawing")


@bp.post("/api/documents/<document_id>/ack-file")
def ingest_ack_document(document_id: str):
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    did = as_uuid(document_id)
    if did is None:
        return jsonify({"error": "invalid document id"}), 400
    row = load_catalog_document(did)
    if row is None:
        return jsonify({"error": "document not found"}), 404
    kind = "drawing" if isinstance(row, Drawing) else "document"
    return _ack_row(row, kind=kind)


def _reject_agent_bytes():
    """Do not parse multipart (that reads the PDF). Reject on Content-Type only."""
    ct = (request.content_type or "").lower()
    if ct.startswith("multipart/form-data"):
        return jsonify(agent_multipart_forbidden_body()), 410
    cl = request.content_length
    if cl is not None and cl > 262_144:
        body = agent_multipart_forbidden_body()
        body["error"]["message"] = (
            "Request is too large for metadata-only ingest. POST JSON, then send bytes to B2."
        )
        return jsonify(body), 413
    return None


def _ingest_metadata() -> dict:
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    if isinstance(payload.get("item"), dict):
        item = dict(payload["item"])
        for key, value in payload.items():
            if key != "item" and key not in item:
                item[key] = value
        payload = item
    if isinstance(payload.get("metadata"), (dict, str)):
        nested = parse_ingest_metadata(payload.get("metadata"))
        merged = dict(nested)
        for key, value in payload.items():
            if key != "metadata" and key not in merged:
                merged[key] = value
        payload = merged
    return payload


def _ingest_register(kind: str):
    denied = _require_ingest_auth()
    if denied is not None:
        return denied
    blocked = _reject_agent_bytes()
    if blocked is not None:
        return blocked
    metadata = _ingest_metadata()
    if not metadata:
        return (
            jsonify(
                {
                    "error": "JSON object required (filename, project_id or folder_name, optional content_hash). File bytes are not accepted.",
                }
            ),
            400,
        )
    try:
        body, status = handle_ingest_register(metadata, kind=kind)
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
        current_app.logger.exception("ingest %s register failed", kind)
        reason = f"{type(exc).__name__}: {exc}"[:400]
        row = _record_bearer_failure(metadata, kind, f"{kind} register failed: {reason}", 500, exc)
        payload = {"error": f"{kind} register failed: {reason}"}
        if row is not None:
            payload["error_id"] = str(row.id)
        return jsonify(payload), 500
    return jsonify(body), status


def _mint_response(row, *, kind: str):
    hint = (
        native_upload_hint_for_drawing(row)
        if kind == "drawing"
        else native_upload_hint_for_document(row)
    )
    if not hint:
        from ..services.object_storage import mint_last_error, mint_retry_after_seconds

        wait = mint_retry_after_seconds() or 20
        current_app.logger.warning(
            "b2 native mint unavailable ingest kind=%s id=%s last_err=%s",
            kind,
            getattr(row, "id", None),
            mint_last_error() or "-",
        )
        body = mint_unavailable_body(kind=kind, detail=mint_last_error() or None)
        resp = jsonify(body)
        resp.status_code = 503
        resp.headers["Retry-After"] = str(wait)
        return resp
    item = serialize_ingest_doc(row, kind=kind, project=None)
    return jsonify({"item": hint, "upload": hint, kind: item, "entity": kind}), 200


def _ack_row(row, *, kind: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        fields = parse_ack_payload(payload)
        if kind == "drawing":
            ack_drawing_file(
                row,
                byte_size=fields["byte_size"],
                content_hash=fields["content_hash"],
                b2_file_id=fields["b2_file_id"],
                b2_file_name=fields["b2_file_name"],
                content_sha1=fields["content_sha1"],
                content_type=fields["content_type"],
            )
        else:
            ack_document_file(
                row,
                byte_size=fields["byte_size"],
                content_hash=fields["content_hash"],
                b2_file_id=fields["b2_file_id"],
                b2_file_name=fields["b2_file_name"],
                content_sha1=fields["content_sha1"],
                content_type=fields["content_type"],
            )
            persist_document_ack(row.id, row)
        db.session.commit()
    except DrawingUploadError as exc:
        db.session.rollback()
        return jsonify({"error": exc.message}), exc.status
    item = serialize_ingest_doc(row, kind=kind, project=None)
    return jsonify({"item": item, kind: item, "entity": kind}), 200


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
