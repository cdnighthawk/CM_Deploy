"""BuildingConnected OAuth + sync routes (Autodesk APS 3-legged)."""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import secrets
import threading
from datetime import datetime, timedelta, timezone

import httpx
from cryptography.fernet import Fernet
from flask import Blueprint, current_app, jsonify, make_response, redirect, request, session
from markupsafe import escape

from ..extensions import db
from ..integrations.autodesk_oauth import (
    build_authorize_url,
    exchange_authorization_code,
    refresh_access_token,
)
from sqlalchemy import func, select

from ..integrations.buildingconnected_client import BuildingConnectedClient
from ..integrations.buildingconnected_write import (
    apply_opportunity_to_lead,
    build_opportunity_patch_body,
    get_submission_change_block_reason,
    message_for_bc_http_error,
)
from ..lead_estimate_csv_load import bc_api_project_to_norm, upsert_lead_estimate_norm_rows
from ..models.buildingconnected_oauth import BuildingConnectedOAuthToken
from ..models.lead_estimate import LeadEstimate

log = logging.getLogger(__name__)

BC_OAUTH_STATE_KEY = "bc_oauth_state"
_SYNC_LOCK = threading.Lock()
_SYNC_RUNNING = False
_PAGE_UPSERT = 100
_BULK_WRITE_MAX = 100


class BcWriteError(Exception):
    def __init__(self, message: str, status: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra or {}


def resolve_lead_for_bc(identifier: str) -> LeadEstimate | None:
    raw = (identifier or "").strip()
    if not raw:
        return None
    try:
        import uuid as uuid_mod

        uid = uuid_mod.UUID(raw)
        row = db.session.get(LeadEstimate, uid)
        if row is not None:
            return row
    except ValueError:
        pass
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == raw))
    if row is not None:
        return row
    return db.session.scalar(
        select(LeadEstimate).where(func.lower(LeadEstimate.external_id) == raw.lower())
    )


def write_lead_opportunity(row: LeadEstimate, data: dict) -> dict:
    """Push submissionState / outcome to BuildingConnected and apply locally."""
    if not isinstance(data, dict):
        raise BcWriteError("expected JSON object body", 400)
    try:
        patch = build_opportunity_patch_body(data)
    except ValueError as exc:
        raise BcWriteError(str(exc), 400) from exc

    outcome_state = None
    if isinstance(row.outcome, dict):
        outcome_state = row.outcome.get("state")
    block = get_submission_change_block_reason(
        external_id=row.external_id,
        submission_state=row.submission_state,
        is_archived=row.is_archived,
        outcome_state=outcome_state,
    )
    if block and patch.get("submissionState"):
        raise BcWriteError(block, 409)
    if not row.external_id:
        raise BcWriteError("This lead is not linked to a BuildingConnected opportunity.", 409)

    try:
        access = _ensure_access_token()
    except Exception as exc:
        log.warning("BuildingConnected write auth failed: %s", exc)
        raise BcWriteError(str(exc), 401) from exc

    base = str(current_app.config.get("BUILDINGCONNECTED_API_BASE") or "").rstrip("/")
    note = str(data.get("note") or "").strip()
    try:
        with BuildingConnectedClient(access, base) as cli:
            try:
                patched = cli.patch_opportunity(row.external_id, patch)
            except httpx.HTTPStatusError as exc:
                if exc.response is None or exc.response.status_code != 401:
                    raise
                _refresh_tokens_unlocked()
                db.session.commit()
                access = _ensure_access_token()
                with BuildingConnectedClient(access, base) as cli2:
                    patched = cli2.patch_opportunity(row.external_id, patch)
                    try:
                        opportunity = cli2.get_opportunity(row.external_id)
                    except Exception:
                        opportunity = patched
            else:
                try:
                    opportunity = cli.get_opportunity(row.external_id)
                except Exception:
                    opportunity = patched
        if not isinstance(opportunity, dict):
            opportunity = patched if isinstance(patched, dict) else {}
        apply_opportunity_to_lead(row, opportunity)
        db.session.commit()
    except httpx.HTTPStatusError as exc:
        db.session.rollback()
        status = exc.response.status_code if exc.response is not None else 502
        try:
            body = exc.response.json() if exc.response is not None else None
        except Exception:
            body = {"raw": (exc.response.text if exc.response is not None else "")[:500]}
        msg = message_for_bc_http_error(status, body, "BuildingConnected PATCH opportunity")
        log.warning("BuildingConnected write failed lead=%s status=%s: %s", row.id, status, msg)
        raise BcWriteError(
            msg, status if 400 <= status < 600 else 502, {"details": body}
        ) from exc
    except BcWriteError:
        raise
    except Exception as exc:
        db.session.rollback()
        log.exception("BuildingConnected write failed")
        raise BcWriteError(str(exc), 502) from exc

    log.info(
        "BuildingConnected write ok lead=%s bc=%s patch=%s note=%s",
        row.id,
        row.external_id,
        patch,
        bool(note),
    )
    from ..api._serializers import lead_estimate_public

    return {
        "ok": True,
        "item": lead_estimate_public(row),
        "opportunity": {
            "id": opportunity.get("id") if isinstance(opportunity, dict) else row.external_id,
            "submissionState": row.submission_state,
            "outcome": row.outcome,
        },
        "entity": "buildingconnected_write",
    }


def cron_secret_matches(req=None, app=None) -> bool:
    """True when X-Cron-Secret matches BC_SYNC_CRON_SECRET (hourly Render job)."""
    cfg = app or current_app
    incoming = req or request
    expected = str(cfg.config.get("BC_SYNC_CRON_SECRET") or "").strip()
    provided = str(incoming.headers.get("X-Cron-Secret") or "").strip()
    if not expected or not provided:
        return False
    return secrets.compare_digest(expected, provided)


def _bc_oauth_browser_page(*, ok: bool, message: str, status: int = 200):
    """HTML landing page after Autodesk redirects back (popup or full tab)."""
    title = "BuildingConnected connected" if ok else "BuildingConnected reconnect failed"
    leads_href = "/construction/leads.html"
    payload = json.dumps(
        {"source": "usis-bc-oauth", "ok": ok, "error": None if ok else message}
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1b242c; }}
    a {{ color: #1f4e5f; }}
    .muted {{ color: #5c6b76; margin-top: 0.75rem; }}
  </style>
</head>
<body>
  <h1 style="font-size:1.25rem">{escape(title)}</h1>
  <p>{escape(message)}</p>
  <p><a href="{leads_href}">Back to Leads</a></p>
  <p class="muted">You can close this window if it does not close on its own.</p>
  <script>
  (function () {{
    var payload = {payload};
    try {{
      if (window.opener && !window.opener.closed) {{
        window.opener.postMessage(payload, window.location.origin);
      }}
    }} catch (e) {{}}
    window.setTimeout(function () {{ window.close(); }}, 80);
  }})();
  </script>
</body>
</html>
"""
    resp = make_response(html, status)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    return resp


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


def _sync_inline() -> bool:
    if current_app.config.get("TESTING"):
        return True
    return (os.environ.get("FLASK_ENV") or "").strip().lower() != "production"


def _opportunities_updated_at_range(*, full: bool) -> str:
    configured = str(
        current_app.config.get("BUILDINGCONNECTED_OPPORTUNITIES_UPDATED_AT") or ""
    ).strip()
    if configured:
        return configured
    if full:
        return "2010-01-01T00:00:00.000Z.."
    start = datetime.now(timezone.utc) - timedelta(days=14)
    return start.strftime("%Y-%m-%dT%H:%M:%S.000Z..")


def _pull_and_upsert(
    access_token: str,
    *,
    full: bool = False,
    max_pages: int | None = None,
) -> tuple[int, int, int]:
    base = str(current_app.config.get("BUILDINGCONNECTED_API_BASE") or "").rstrip("/")
    updated_at_range = _opportunities_updated_at_range(full=full)
    page_cap = int(max_pages) if max_pages is not None else (500 if full else 50)
    seen: set[str] = set()
    batch: list[dict[str, str | None]] = []
    loaded = skipped = errors = 0

    def flush() -> None:
        nonlocal loaded, skipped, errors, batch
        if not batch:
            return
        l, s, e = upsert_lead_estimate_norm_rows(db.session, batch)
        loaded += l
        skipped += s
        errors += e
        batch = []
        db.session.expunge_all()

    log.info(
        "BuildingConnected pull full=%s pages=%s updatedAt=%s",
        full,
        page_cap,
        updated_at_range,
    )
    with BuildingConnectedClient(access_token, base) as cli:
        for item in cli.iter_opportunities(
            updated_at_range=updated_at_range,
            max_pages=page_cap,
        ):
            norm = bc_api_project_to_norm(item)
            oid = norm.get("id")
            if isinstance(oid, str) and oid:
                if oid in seen:
                    continue
                seen.add(oid)
            batch.append(norm)
            if len(batch) >= _PAGE_UPSERT:
                flush()
        flush()
    return loaded, skipped, errors


def _run_sync_job(app, access_token: str, *, full: bool = False) -> None:
    global _SYNC_RUNNING
    with app.app_context():
        try:
            loaded, skipped, errors = _pull_and_upsert(access_token, full=full)
            db.session.commit()
            log.info(
                "BuildingConnected sync complete: loaded=%s skipped=%s errors=%s full=%s",
                loaded,
                skipped,
                errors,
                full,
            )
        except httpx.HTTPStatusError as exc:
            db.session.rollback()
            if exc.response is not None and exc.response.status_code == 401:
                log.warning("BuildingConnected background sync 401; refreshing token and retrying")
                try:
                    _refresh_tokens_unlocked()
                    db.session.commit()
                    token = _ensure_access_token()
                    loaded, skipped, errors = _pull_and_upsert(token, full=full)
                    db.session.commit()
                    log.info(
                        "BuildingConnected sync complete after refresh: loaded=%s skipped=%s errors=%s",
                        loaded,
                        skipped,
                        errors,
                    )
                except Exception:
                    db.session.rollback()
                    log.exception("BuildingConnected background sync failed after 401 retry")
            else:
                log.exception("BuildingConnected background sync HTTP error")
        except Exception:
            db.session.rollback()
            log.exception("BuildingConnected background sync failed")
            log.info(
                "BuildingConnected sync complete: loaded=%s skipped=%s errors=%s",
                loaded,
                skipped,
                errors,
            )
        except Exception:
            db.session.rollback()
            log.exception("BuildingConnected background sync failed")
        finally:
            with _SYNC_LOCK:
                _SYNC_RUNNING = False


def register_buildingconnected_routes(bp: Blueprint) -> None:
    @bp.get("/integrations/buildingconnected/oauth/start")
    def bc_oauth_start():
        cid = current_app.config.get("AUTODESK_CLIENT_ID")
        redir = current_app.config.get("AUTODESK_OAUTH_REDIRECT_URI")
        scopes = str(current_app.config.get("AUTODESK_OAUTH_SCOPES") or "data:read data:write")
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
            return _bc_oauth_browser_page(ok=False, message=err, status=400)
        code = (request.args.get("code") or "").strip()
        state = (request.args.get("state") or "").strip()
        expected = session.pop(BC_OAUTH_STATE_KEY, None)
        if not code or not state or expected != state:
            return _bc_oauth_browser_page(
                ok=False, message="invalid or missing OAuth state/code", status=400
            )
        cid = current_app.config.get("AUTODESK_CLIENT_ID")
        sec = current_app.config.get("AUTODESK_CLIENT_SECRET")
        redir = current_app.config.get("AUTODESK_OAUTH_REDIRECT_URI")
        if not cid or not sec or not redir:
            return _bc_oauth_browser_page(
                ok=False, message="Autodesk client is not fully configured", status=503
            )
        try:
            data = exchange_authorization_code(
                client_id=cid, client_secret=sec, code=code, redirect_uri=redir
            )
            _persist_token_payload(data)
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            log.warning("BuildingConnected OAuth callback failed: %s", exc)
            return _bc_oauth_browser_page(ok=False, message=str(exc), status=400)
        return _bc_oauth_browser_page(
            ok=True, message="BuildingConnected is connected. You can return to Leads."
        )

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
        want_full = (request.args.get("full") or "").strip().lower() in ("1", "true", "yes")
        if not _sync_inline():
            global _SYNC_RUNNING
            with _SYNC_LOCK:
                if _SYNC_RUNNING:
                    return (
                        jsonify(
                            {
                                "ok": True,
                                "status": "already_running",
                                "entity": "buildingconnected_sync",
                                "message": "A BuildingConnected sync is already running. Refresh Leads in a minute.",
                            }
                        ),
                        202,
                    )
                _SYNC_RUNNING = True
            app = current_app._get_current_object()
            threading.Thread(
                target=_run_sync_job,
                args=(app, access),
                kwargs={"full": want_full},
                daemon=True,
                name="bc-sync",
            ).start()
            return (
                jsonify(
                    {
                        "ok": True,
                        "status": "started",
                        "full": want_full,
                        "entity": "buildingconnected_sync",
                        "message": (
                            "Full Bid Board history sync is running in the background. Check Leads in 15–30 minutes."
                            if want_full
                            else "Recent Bid Board sync is running in the background. Refresh Leads in about a minute."
                        ),
                    }
                ),
                202,
            )
        try:
            loaded, skipped, errors = _pull_and_upsert(access, full=want_full)
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

    def _write_disabled_response():
        return (
            jsonify(
                {
                    "error": "BuildingConnected write-back is disabled (set BC_WRITE_ENABLED=1).",
                    "entity": "buildingconnected_write",
                }
            ),
            403,
        )

    def _bc_write_error_response(exc: BcWriteError):
        body = {"error": exc.message, "entity": "buildingconnected_write"}
        body.update(exc.extra)
        lowered = exc.message.lower()
        if "reconnect" in lowered or "privilege" in lowered or "data:write" in lowered:
            body["reconnect_url"] = "/api/v1/integrations/buildingconnected/oauth/start"
        return jsonify(body), exc.status

    @bp.post("/lead-estimates/bulk/buildingconnected")
    def bulk_patch_lead_buildingconnected():
        """Push the same submissionState / outcome to several BuildingConnected opportunities."""
        if not current_app.config.get("BC_WRITE_ENABLED"):
            return _write_disabled_response()
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "expected JSON object body", "entity": "buildingconnected_write"}), 400
        raw_ids = data.get("ids") or data.get("lead_ids") or []
        if not isinstance(raw_ids, list) or not raw_ids:
            return jsonify({"error": "ids must be a non-empty list", "entity": "buildingconnected_write"}), 400
        if len(raw_ids) > _BULK_WRITE_MAX:
            return (
                jsonify(
                    {
                        "error": f"ids cannot exceed {_BULK_WRITE_MAX}",
                        "entity": "buildingconnected_write",
                    }
                ),
                400,
            )
        try:
            build_opportunity_patch_body(data)
        except ValueError as exc:
            return jsonify({"error": str(exc), "entity": "buildingconnected_write"}), 400

        updated: list[dict] = []
        failed: list[dict] = []
        for raw in raw_ids:
            ident = str(raw or "").strip()
            row = resolve_lead_for_bc(ident)
            if row is None:
                failed.append({"id": ident, "error": "lead estimate not found"})
                continue
            try:
                result = write_lead_opportunity(row, data)
                item = result.get("item") or {}
                updated.append(
                    {
                        "id": str(row.id),
                        "external_id": row.external_id,
                        "submission_state": row.submission_state,
                        "item": item,
                    }
                )
            except BcWriteError as exc:
                failed.append({"id": str(row.id), "error": exc.message})

        return jsonify(
            {
                "ok": True,
                "updated": updated,
                "failed": failed,
                "updated_count": len(updated),
                "failed_count": len(failed),
                "entity": "buildingconnected_write",
            }
        )

    @bp.patch("/lead-estimates/<identifier>/buildingconnected")
    def patch_lead_buildingconnected(identifier: str):
        """
        Push submissionState / outcome to BuildingConnected.

        curl -X PATCH https://www.usiscm.com/api/v1/lead-estimates/BC_ID/buildingconnected \\
          -H "Content-Type: application/json" \\
          -d '{"submissionState":"DECLINED","note":"Outside service area"}'
        """
        if not current_app.config.get("BC_WRITE_ENABLED"):
            return _write_disabled_response()
        row = resolve_lead_for_bc(identifier)
        if row is None:
            return jsonify({"error": "lead estimate not found", "entity": "buildingconnected_write"}), 404
        data = request.get_json(silent=True)
        if not isinstance(data, dict):
            return jsonify({"error": "expected JSON object body", "entity": "buildingconnected_write"}), 400
        try:
            payload = write_lead_opportunity(row, data)
        except BcWriteError as exc:
            return _bc_write_error_response(exc)
        return jsonify(payload)
