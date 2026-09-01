"""Record and list website connection failures and similar errors."""
from __future__ import annotations

import hashlib
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import current_app, has_request_context, request
from sqlalchemy import func, select
from werkzeug.exceptions import HTTPException

from ..extensions import db
from ..models import User
from ..models.client_error import ClientErrorEvent
from ._admin_users_service import ApiError, _iso, _require_admin
from ._perms import CurrentUser

ALLOWED_KINDS = frozenset({"connect", "http_error", "js_error", "unhandled", "server"})
ALLOWED_SOURCES = frozenset({"browser", "server"})

_MAX_MESSAGE = 2000
_MAX_URL = 1000
_MAX_PAGE = 500
_MAX_UA = 500
_MAX_METHOD = 10
_MAX_BATCH = 20
_DEDUP_SECONDS = 120
_RATE_WINDOW_SECONDS = 60
_RATE_MAX_PER_IP = 40

_rate: dict[str, deque[float]] = defaultdict(deque)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clip(value: Any, n: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:n]


def _parse_occurred_at(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        dt = raw
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    if isinstance(raw, (int, float)):
        try:
            ms = float(raw)
            if ms > 1e12:
                ms = ms / 1000.0
            return datetime.fromtimestamp(ms, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return _now()
    if isinstance(raw, str) and raw.strip():
        text = raw.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return _now()
    return _now()


def _fingerprint(kind: str, url: str | None, message: str) -> str:
    raw = f"{kind}|{url or ''}|{message}".encode("utf-8", errors="replace")
    return hashlib.sha256(raw).hexdigest()[:64]


def _client_ip() -> str | None:
    if not has_request_context():
        return None
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    if forwarded:
        return forwarded[:45]
    return (request.remote_addr or "")[:45] or None


def _rate_limited(ip: str | None) -> bool:
    if not ip:
        return False
    now = _now().timestamp()
    bucket = _rate[ip]
    cutoff = now - _RATE_WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= _RATE_MAX_PER_IP:
        return True
    bucket.append(now)
    return False


def _parse_status(raw: Any) -> int | None:
    if raw is None or raw == "":
        return None
    try:
        n = int(raw)
    except (TypeError, ValueError):
        return None
    if n < 0 or n > 999:
        return None
    return n


def _normalize_event(data: dict[str, Any], *, default_source: str) -> dict[str, Any] | None:
    kind = str(data.get("kind") or "").strip().lower()
    if kind not in ALLOWED_KINDS:
        return None
    message = _clip(data.get("message") or data.get("error") or "Unknown error", _MAX_MESSAGE)
    if not message:
        return None
    source = str(data.get("source") or default_source).strip().lower()
    if source not in ALLOWED_SOURCES:
        source = default_source
    url = _clip(data.get("url") or data.get("href"), _MAX_URL)
    method = _clip((data.get("method") or "").upper(), _MAX_METHOD)
    page = _clip(data.get("page") or data.get("pageUrl") or data.get("path"), _MAX_PAGE)
    extra = data.get("extra")
    if extra is not None and not isinstance(extra, dict):
        extra = {"value": str(extra)[:500]}
    return {
        "source": source,
        "kind": kind,
        "message": message,
        "url": url,
        "method": method,
        "http_status": _parse_status(data.get("status") if "status" in data else data.get("http_status")),
        "page": page,
        "user_agent": _clip(data.get("user_agent") or data.get("userAgent"), _MAX_UA),
        "extra": extra,
        "occurred_at": _parse_occurred_at(data.get("occurred_at") or data.get("timestamp")),
        "fingerprint": _fingerprint(kind, url, message),
    }


def _recent_duplicate(fingerprint: str, ip: str | None, user_id: uuid.UUID | None) -> bool:
    cutoff = _now() - timedelta(seconds=_DEDUP_SECONDS)
    stmt = select(ClientErrorEvent.id).where(
        ClientErrorEvent.fingerprint == fingerprint,
        ClientErrorEvent.created_at >= cutoff,
    )
    if user_id is not None:
        stmt = stmt.where(ClientErrorEvent.user_id == user_id)
    elif ip:
        stmt = stmt.where(ClientErrorEvent.ip_address == ip)
    return db.session.scalar(stmt.limit(1)) is not None


def _insert(fields: dict[str, Any], *, user_id: uuid.UUID | None, ip: str | None, ua: str | None) -> ClientErrorEvent | None:
    if _recent_duplicate(fields["fingerprint"], ip, user_id):
        return None
    row = ClientErrorEvent(
        user_id=user_id,
        source=fields["source"],
        kind=fields["kind"],
        message=fields["message"],
        url=fields["url"],
        method=fields["method"],
        http_status=fields["http_status"],
        page=fields["page"],
        fingerprint=fields["fingerprint"],
        ip_address=ip,
        user_agent=fields["user_agent"] or ua,
        extra=fields["extra"],
        occurred_at=fields["occurred_at"],
    )
    db.session.add(row)
    try:
        current_app.logger.warning(
            "client_error kind=%s source=%s status=%s url=%s page=%s msg=%s",
            row.kind,
            row.source,
            row.http_status,
            (row.url or "")[:200],
            (row.page or "")[:120],
            (row.message or "")[:300],
        )
    except RuntimeError:
        pass
    return row


def ingest_payload(cu: CurrentUser, payload: Any) -> dict[str, Any]:
    ip = _client_ip()
    if _rate_limited(ip):
        raise ApiError("Too many error reports. Try again shortly.", 429)
    if isinstance(payload, list):
        events = payload
    elif isinstance(payload, dict) and isinstance(payload.get("events"), list):
        events = payload["events"]
    elif isinstance(payload, dict):
        events = [payload]
    else:
        raise ApiError("JSON object or events array required", 400)
    if not events:
        raise ApiError("No events provided", 400)
    ua = None
    if has_request_context():
        ua = _clip(request.headers.get("User-Agent"), _MAX_UA)
    user_id = cu.user.id if cu.user is not None else None
    stored = 0
    skipped = 0
    for raw in events[:_MAX_BATCH]:
        if not isinstance(raw, dict):
            skipped += 1
            continue
        fields = _normalize_event(raw, default_source="browser")
        if fields is None:
            skipped += 1
            continue
        row = _insert(fields, user_id=user_id, ip=ip, ua=ua)
        if row is None:
            skipped += 1
        else:
            stored += 1
    if stored:
        db.session.commit()
    return {"ok": True, "stored": stored, "skipped": skipped, "entity": "client_error"}


def record_from_exception(exc: BaseException) -> None:
    """Best-effort persist of an unhandled Flask exception. Never raises."""
    if isinstance(exc, HTTPException) and (exc.code or 500) < 500:
        return
    try:
        db.session.rollback()
    except Exception:
        pass
    try:
        cu_user_id = None
        if has_request_context():
            from ._perms import current_user

            try:
                u = current_user().user
                cu_user_id = u.id if u is not None else None
            except Exception:
                cu_user_id = None
        url = None
        method = None
        page = None
        ua = None
        ip = _client_ip()
        if has_request_context():
            url = _clip(request.path, _MAX_URL)
            method = _clip(request.method, _MAX_METHOD)
            page = _clip(request.headers.get("Referer"), _MAX_PAGE)
            ua = _clip(request.headers.get("User-Agent"), _MAX_UA)
        status = getattr(exc, "code", None)
        if not isinstance(status, int):
            status = 500
        message = _clip(f"{type(exc).__name__}: {exc}", _MAX_MESSAGE) or "Unhandled server exception"
        fields = _normalize_event(
            {
                "source": "server",
                "kind": "server",
                "message": message,
                "url": url,
                "method": method,
                "status": status,
                "page": page,
            },
            default_source="server",
        )
        if fields is None:
            return
        row = _insert(fields, user_id=cu_user_id, ip=ip, ua=ua)
        if row is not None:
            db.session.commit()
    except Exception:
        try:
            db.session.rollback()
        except Exception:
            pass
        try:
            current_app.logger.exception("failed to persist server error event")
        except RuntimeError:
            pass


def _event_public(row: ClientErrorEvent, user: User | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "user_id": str(row.user_id) if row.user_id else None,
        "source": row.source,
        "kind": row.kind,
        "message": row.message,
        "url": row.url,
        "method": row.method,
        "http_status": row.http_status,
        "page": row.page,
        "ip_address": row.ip_address,
        "occurred_at": _iso(row.occurred_at),
        "created_at": _iso(row.created_at),
        "extra": row.extra,
    }
    if user is not None:
        name = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
        out["user_name"] = name or user.email
        out["user_email"] = user.email
    elif row.user_id is None:
        out["user_name"] = "Anonymous"
        out["user_email"] = None
    return out


def list_events(
    cu: CurrentUser,
    *,
    kind: str | None = None,
    source: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    _require_admin(cu)
    stmt = select(ClientErrorEvent)
    count_stmt = select(func.count()).select_from(ClientErrorEvent)
    if kind:
        stmt = stmt.where(ClientErrorEvent.kind == kind)
        count_stmt = count_stmt.where(ClientErrorEvent.kind == kind)
    if source:
        stmt = stmt.where(ClientErrorEvent.source == source)
        count_stmt = count_stmt.where(ClientErrorEvent.source == source)
    if since is not None:
        stmt = stmt.where(ClientErrorEvent.occurred_at >= since)
        count_stmt = count_stmt.where(ClientErrorEvent.occurred_at >= since)
    total = int(db.session.scalar(count_stmt) or 0)
    rows = db.session.scalars(
        stmt.order_by(ClientErrorEvent.occurred_at.desc()).offset(offset).limit(limit)
    ).all()
    user_ids = {r.user_id for r in rows if r.user_id}
    users: dict[uuid.UUID, User] = {}
    if user_ids:
        for u in db.session.scalars(select(User).where(User.id.in_(user_ids))).all():
            users[u.id] = u
    return [_event_public(r, users.get(r.user_id) if r.user_id else None) for r in rows], total


def _err(exc: ApiError):
    from flask import jsonify

    return jsonify({"error": exc.message}), exc.status


def register_client_error_routes(bp) -> None:
    from flask import jsonify, request as req

    from ._perms import current_user

    @bp.post("/client-errors")
    def post_client_errors():
        body = req.get_json(silent=True)
        try:
            return jsonify(ingest_payload(current_user(), body))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/admin/client-errors")
    def admin_list_client_errors():
        kind = (req.args.get("kind") or "").strip().lower() or None
        if kind and kind not in ALLOWED_KINDS:
            return jsonify({"error": "invalid kind"}), 400
        source = (req.args.get("source") or "").strip().lower() or None
        if source and source not in ALLOWED_SOURCES:
            return jsonify({"error": "invalid source"}), 400
        try:
            limit = max(1, min(int(req.args.get("limit") or 100), 500))
            offset = max(0, int(req.args.get("offset") or 0))
            days = max(1, min(int(req.args.get("days") or 7), 90))
        except ValueError:
            return jsonify({"error": "invalid limit, offset, or days"}), 400
        since = _now() - timedelta(days=days)
        try:
            items, total = list_events(
                current_user(),
                kind=kind,
                source=source,
                since=since,
                limit=limit,
                offset=offset,
            )
        except ApiError as exc:
            return _err(exc)
        return jsonify(
            {
                "items": items,
                "total": total,
                "limit": limit,
                "offset": offset,
                "days": days,
                "entity": "client_error",
            }
        )
