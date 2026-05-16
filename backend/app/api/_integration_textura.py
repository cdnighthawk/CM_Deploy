"""Textura TPM integration routes (credentials + pull sync)."""
from __future__ import annotations

import base64
import hashlib
import logging
import uuid
from datetime import datetime, timezone

from cryptography.fernet import Fernet
from flask import Blueprint, current_app, jsonify, request
from sqlalchemy import select

from ..extensions import db
from ..integrations.textura_client import TexturaClient
from ..integrations.textura_sync import SyncCounts, sync_all, sync_invoices, sync_projects
from ..models import Project, TexturaCredential, TexturaSyncLog

log = logging.getLogger(__name__)


def _fernet() -> Fernet:
    raw = (current_app.config.get("TOKEN_ENCRYPTION_KEY") or "").strip()
    if raw:
        seed = raw
    else:
        seed = str(current_app.config.get("SECRET_KEY") or "dev")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest())
    return Fernet(key)


def _encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def _decrypt_secret(blob: str) -> str:
    return _fernet().decrypt(blob.encode()).decode()


def _textura_base_url(override: str | None = None) -> str:
    if override and override.strip():
        return override.strip().rstrip("/")
    return str(current_app.config.get("TEXTURA_API_BASE") or "").rstrip("/")


def _resolve_credentials() -> tuple[str, str, str] | None:
    row = db.session.get(TexturaCredential, "default")
    if row is not None:
        try:
            password = _decrypt_secret(row.password_encrypted)
        except Exception:
            return None
        base = _textura_base_url(row.api_base)
        return row.username, password, base

    user = (current_app.config.get("TEXTURA_USERNAME") or "").strip()
    password = (current_app.config.get("TEXTURA_PASSWORD") or "").strip()
    if user and password:
        return user, password, _textura_base_url()
    return None


def _client_from_credentials() -> TexturaClient:
    creds = _resolve_credentials()
    if creds is None:
        raise RuntimeError("Textura is not configured (save credentials or set TEXTURA_USERNAME/PASSWORD).")
    user, password, base = creds
    if not base:
        raise RuntimeError("TEXTURA_API_BASE is not configured.")
    return TexturaClient(
        base,
        user,
        password,
        poll_interval_sec=float(current_app.config.get("TEXTURA_POLL_INTERVAL_SEC") or 2),
        poll_timeout_sec=float(current_app.config.get("TEXTURA_POLL_TIMEOUT_SEC") or 300),
    )


def _finish_sync_log(log_row: TexturaSyncLog, counts: SyncCounts, *, status: str = "success") -> None:
    log_row.finished_at = datetime.now(timezone.utc)
    log_row.loaded = counts.loaded
    log_row.skipped = counts.skipped
    log_row.errors = counts.errors
    log_row.error_details = counts.error_details or None
    if counts.errors and counts.loaded:
        log_row.status = "partial"
    elif counts.errors:
        log_row.status = "failed"
    else:
        log_row.status = status


def _sync_response(counts: SyncCounts, entity: str) -> dict:
    return {
        "ok": counts.errors == 0 or counts.loaded > 0,
        "loaded": counts.loaded,
        "skipped": counts.skipped,
        "errors": counts.errors,
        "error_details": counts.error_details,
        "entity": entity,
    }


def _run_sync(
    *,
    entity_type: str,
    fn,
    project_id: uuid.UUID | None = None,
) -> tuple[SyncCounts, int]:
    if not current_app.config.get("TEXTURA_SYNC_ENABLED"):
        return SyncCounts(), 403

    started = datetime.now(timezone.utc)
    try:
        with _client_from_credentials() as client:
            counts = fn(client)
        log_row = TexturaSyncLog(
            direction="export",
            entity_type=entity_type,
            project_id=project_id,
            started_at=started,
            finished_at=datetime.now(timezone.utc),
            status="running",
        )
        db.session.add(log_row)
        db.session.flush()
        _finish_sync_log(log_row, counts)
        db.session.commit()
        code = 200 if counts.errors == 0 or counts.loaded > 0 else 502
        return counts, code
    except Exception as exc:
        db.session.rollback()
        log.warning("Textura sync failed: %s", exc)
        counts = SyncCounts(errors=1, error_details=[{"entity": entity_type, "message": str(exc)}])
        try:
            log_row = TexturaSyncLog(
                direction="export",
                entity_type=entity_type,
                project_id=project_id,
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                status="failed",
                errors=1,
                error_details=counts.error_details,
            )
            db.session.add(log_row)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return counts, 502


def register_textura_routes(bp: Blueprint) -> None:
    @bp.get("/integrations/textura/status")
    def textura_status():
        creds = _resolve_credentials()
        cred_row = db.session.get(TexturaCredential, "default")
        last = db.session.scalars(
            select(TexturaSyncLog).order_by(TexturaSyncLog.started_at.desc()).limit(1)
        ).first()
        last_payload = None
        if last is not None:
            last_payload = {
                "id": str(last.id),
                "entity_type": last.entity_type,
                "status": last.status,
                "loaded": last.loaded,
                "skipped": last.skipped,
                "errors": last.errors,
                "started_at": last.started_at.isoformat() if last.started_at else None,
                "finished_at": last.finished_at.isoformat() if last.finished_at else None,
            }
        api_base = _textura_base_url(cred_row.api_base if cred_row and cred_row.api_base else None)
        return jsonify(
            {
                "configured": creds is not None,
                "sync_enabled": bool(current_app.config.get("TEXTURA_SYNC_ENABLED")),
                "api_base": api_base or None,
                "last_sync": last_payload,
                "entity": "textura_status",
            }
        )

    @bp.put("/integrations/textura/credentials")
    def textura_put_credentials():
        data = request.get_json(silent=True) or {}
        username = str(data.get("username") or "").strip()
        password = str(data.get("password") or "").strip()
        if not username or not password:
            return jsonify({"error": "username and password are required", "entity": "textura_credentials"}), 400
        api_base = str(data.get("api_base") or "").strip() or None
        enc = _encrypt_secret(password)
        row = db.session.get(TexturaCredential, "default")
        if row is None:
            db.session.add(
                TexturaCredential(
                    label="default",
                    username=username,
                    password_encrypted=enc,
                    api_base=api_base,
                )
            )
        else:
            row.username = username
            row.password_encrypted = enc
            if api_base is not None:
                row.api_base = api_base or None
        db.session.commit()
        return jsonify({"ok": True, "entity": "textura_credentials"})

    @bp.delete("/integrations/textura/credentials")
    def textura_delete_credentials():
        row = db.session.get(TexturaCredential, "default")
        if row is not None:
            db.session.delete(row)
            db.session.commit()
        return jsonify({"ok": True, "entity": "textura_credentials"})

    @bp.post("/integrations/textura/test-connection")
    def textura_test_connection():
        try:
            with _client_from_credentials() as client:
                client.test_connection()
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc), "entity": "textura_connection"}), 400
        return jsonify({"ok": True, "entity": "textura_connection"})

    @bp.route("/integrations/textura/sync", methods=["GET", "POST"])
    def textura_sync_all():
        auto_create = bool(current_app.config.get("TEXTURA_AUTO_CREATE_PROJECTS"))

        def _do(client: TexturaClient) -> SyncCounts:
            return sync_all(db.session, client, auto_create_projects=auto_create)

        counts, code = _run_sync(entity_type="all", fn=_do)
        return jsonify(_sync_response(counts, "textura_sync")), code

    @bp.route("/integrations/textura/sync/projects", methods=["POST"])
    def textura_sync_projects():
        auto_create = bool(current_app.config.get("TEXTURA_AUTO_CREATE_PROJECTS"))

        def _do(client: TexturaClient) -> SyncCounts:
            return sync_projects(db.session, client, auto_create=auto_create)

        counts, code = _run_sync(entity_type="projects", fn=_do)
        return jsonify(_sync_response(counts, "textura_sync_projects")), code

    @bp.route("/integrations/textura/sync/invoices", methods=["POST"])
    def textura_sync_invoices():
        def _do(client: TexturaClient) -> SyncCounts:
            return sync_invoices(db.session, client)

        counts, code = _run_sync(entity_type="invoices", fn=_do)
        return jsonify(_sync_response(counts, "textura_sync_invoices")), code

    @bp.route("/projects/<project_id>/integrations/textura/sync", methods=["POST"])
    def textura_sync_project(project_id: str):
        try:
            pid = uuid.UUID(project_id)
        except ValueError:
            return jsonify({"error": "invalid project id", "entity": "textura_sync"}), 400
        proj = db.session.get(Project, pid)
        if proj is None or proj.deleted_at is not None:
            return jsonify({"error": "project not found", "entity": "textura_sync"}), 404
        auto_create = bool(current_app.config.get("TEXTURA_AUTO_CREATE_PROJECTS"))

        def _do(client: TexturaClient) -> SyncCounts:
            total = SyncCounts()
            p = sync_projects(db.session, client, auto_create=auto_create)
            total.merge(p)
            inv = sync_invoices(db.session, client, project_id=pid)
            total.merge(inv)
            return total

        counts, code = _run_sync(entity_type="project", fn=_do, project_id=pid)
        return jsonify(_sync_response(counts, "textura_sync")), code
