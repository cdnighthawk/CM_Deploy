"""BuildingConnected OAuth + sync routes (Autodesk APS 3-legged)."""
from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet
from flask import Blueprint, current_app, jsonify, redirect, request, session

from ..extensions import db
from ..integrations.autodesk_oauth import (
    build_authorize_url,
    exchange_authorization_code,
    refresh_access_token,
)
from ..integrations.buildingconnected_client import BuildingConnectedClient
from ..lead_estimate_csv_load import bc_api_project_to_norm, upsert_lead_estimate_norm_rows
from ..models.buildingconnected_oauth import BuildingConnectedOAuthToken

log = logging.getLogger(__name__)

BC_OAUTH_STATE_KEY = "bc_oauth_state"


def _fernet() -> Fernet:
    raw = (current_app.config.get("TOKEN_ENCRYPTION_KEY") or "").strip()
    if raw:
        seed = raw
    else:
        seed = str(current_app.config.get("SECRET_KEY") or "dev")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed.encode()).digest())
    return Fernet(key)


def _encrypt_refresh(refresh_token: str) -> str:
    return _fernet().encrypt(refresh_token.encode()).decode()


def _decrypt_refresh(blob: str) -> str:
    return _fernet().decrypt(blob.encode()).decode()


def _persist_token_payload(data: dict) -> None:
    at = data.get("access_token")
    refresh = data.get("refresh_token")
    expires_in = int(data.get("expires_in") or 0)
    if not isinstance(at, str) or not isinstance(refresh, str):
        raise ValueError("token response missing access_token or refresh_token")
    exp: datetime | None = None
    if expires_in > 0:
        exp = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 120))
    row = db.session.get(BuildingConnectedOAuthToken, "default")
    enc = _encrypt_refresh(refresh)
    if row is None:
        db.session.add(
            BuildingConnectedOAuthToken(
                label="default",
                refresh_token_encrypted=enc,
                access_token=at,
                access_expires_at=exp,
            )
        )
    else:
        row.refresh_token_encrypted = enc
        row.access_token = at
        row.access_expires_at = exp


def _refresh_tokens_unlocked() -> None:
    row = db.session.get(BuildingConnectedOAuthToken, "default")
    if row is None:
        raise RuntimeError("BuildingConnected is not connected (complete OAuth first).")
    rt = _decrypt_refresh(row.refresh_token_encrypted)
    cid = current_app.config.get("AUTODESK_CLIENT_ID")
    sec = current_app.config.get("AUTODESK_CLIENT_SECRET")
    if not cid or not sec:
        raise RuntimeError("AUTODESK_CLIENT_ID / AUTODESK_CLIENT_SECRET are not configured.")
    data = refresh_access_token(client_id=cid, client_secret=sec, refresh_token=rt)
    row.access_token = data.get("access_token")
    if not isinstance(row.access_token, str):
        raise ValueError("refresh response missing access_token")
    expires_in = int(data.get("expires_in") or 0)
    if expires_in > 0:
        row.access_expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(0, expires_in - 120))
    new_rt = data.get("refresh_token")
    if isinstance(new_rt, str) and new_rt.strip():
        row.refresh_token_encrypted = _encrypt_refresh(new_rt)


def _ensure_access_token() -> str:
    row = db.session.get(BuildingConnectedOAuthToken, "default")
    if row is None:
        raise RuntimeError("BuildingConnected is not connected (complete OAuth first).")
    now = datetime.now(timezone.utc)
    if (
        row.access_token
        and row.access_expires_at
        and row.access_expires_at > now + timedelta(seconds=30)
    ):
        return row.access_token
    _refresh_tokens_unlocked()
    db.session.commit()
    if not row.access_token:
        raise RuntimeError("failed to obtain access token after refresh")
    return row.access_token


def _pull_and_upsert(access_token: str) -> tuple[int, int, int]:
    base = str(current_app.config.get("BUILDINGCONNECTED_API_BASE") or "").rstrip("/")
    include_closed = bool(current_app.config.get("BUILDINGCONNECTED_INCLUDE_CLOSED"))
    norms: list[dict[str, str | None]] = []
    with BuildingConnectedClient(access_token, base) as cli:
        for proj in cli.iter_projects(include_closed=include_closed):
            norms.append(bc_api_project_to_norm(proj))
    return upsert_lead_estimate_norm_rows(db.session, norms)


def register_buildingconnected_routes(bp: Blueprint) -> None:
    @bp.get("/integrations/buildingconnected/oauth/start")
    def bc_oauth_start():
        cid = current_app.config.get("AUTODESK_CLIENT_ID")
        redir = current_app.config.get("AUTODESK_OAUTH_REDIRECT_URI")
        scopes = str(current_app.config.get("AUTODESK_OAUTH_SCOPES") or "data:read")
        if not cid or not redir:
            return (
                jsonify(
                    {
                        "error": "AUTODESK_CLIENT_ID and AUTODESK_OAUTH_REDIRECT_URI must be set",
                        "entity": "buildingconnected_oauth",
                    }
                ),
                503,
            )
        state = secrets.token_urlsafe(32)
        session[BC_OAUTH_STATE_KEY] = state
        session.permanent = True
        url = build_authorize_url(client_id=cid, redirect_uri=redir, scopes=scopes, state=state)
        return redirect(url, code=302)

    @bp.get("/integrations/buildingconnected/oauth/callback")
    def bc_oauth_callback():
        err = (request.args.get("error") or "").strip()
        if err:
            return jsonify({"error": err, "entity": "buildingconnected_oauth"}), 400
        code = (request.args.get("code") or "").strip()
        state = (request.args.get("state") or "").strip()
        expected = session.pop(BC_OAUTH_STATE_KEY, None)
        if not code or not state or expected != state:
            return jsonify({"error": "invalid or missing OAuth state/code", "entity": "buildingconnected_oauth"}), 400
        cid = current_app.config.get("AUTODESK_CLIENT_ID")
        sec = current_app.config.get("AUTODESK_CLIENT_SECRET")
        redir = current_app.config.get("AUTODESK_OAUTH_REDIRECT_URI")
        if not cid or not sec or not redir:
            return jsonify({"error": "Autodesk client is not fully configured", "entity": "buildingconnected_oauth"}), 503
        try:
            data = exchange_authorization_code(
                client_id=cid, client_secret=sec, code=code, redirect_uri=redir
            )
            _persist_token_payload(data)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            log.warning("BuildingConnected OAuth callback failed: %s", exc)
            return jsonify({"error": str(exc), "entity": "buildingconnected_oauth"}), 400
        return jsonify({"ok": True, "entity": "buildingconnected_oauth"})

    @bp.route("/integrations/buildingconnected/sync", methods=["GET", "POST"])
    def bc_sync():
        if not current_app.config.get("BUILDINGCONNECTED_SYNC_ENABLED"):
            return (
                jsonify(
                    {
                        "error": "BuildingConnected sync is disabled (set BUILDINGCONNECTED_SYNC_ENABLED=1)",
                        "entity": "buildingconnected_sync",
                    }
                ),
                403,
            )
        try:
            access = _ensure_access_token()
        except Exception as exc:
            log.warning("BuildingConnected sync auth failed: %s", exc)
            return jsonify({"error": str(exc), "entity": "buildingconnected_sync"}), 401
        try:
            loaded, skipped, errors = _pull_and_upsert(access)
            db.session.commit()
        except httpx.HTTPStatusError as exc:
            db.session.rollback()
            if exc.response is not None and exc.response.status_code == 401:
                try:
                    _refresh_tokens_unlocked()
                    db.session.commit()
                    row = db.session.get(BuildingConnectedOAuthToken, "default")
                    if not row or not row.access_token:
                        raise RuntimeError("no access token after refresh") from None
                    loaded, skipped, errors = _pull_and_upsert(row.access_token)
                    db.session.commit()
                except Exception as exc2:
                    db.session.rollback()
                    log.warning("BuildingConnected sync failed after 401 retry: %s", exc2)
                    return jsonify({"error": str(exc2), "entity": "buildingconnected_sync"}), 502
            else:
                log.warning("BuildingConnected sync HTTP error: %s", exc)
                return jsonify({"error": str(exc), "entity": "buildingconnected_sync"}), 502
        except Exception as exc:
            db.session.rollback()
            log.warning("BuildingConnected sync failed: %s", exc)
            return jsonify({"error": str(exc), "entity": "buildingconnected_sync"}), 502
        log.info(
            "BuildingConnected sync complete: loaded=%s skipped=%s errors=%s",
            loaded,
            skipped,
            errors,
        )
        return jsonify(
            {
                "ok": True,
                "loaded": loaded,
                "skipped": skipped,
                "errors": errors,
                "entity": "buildingconnected_sync",
            }
        )
