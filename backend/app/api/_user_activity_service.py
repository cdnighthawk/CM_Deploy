"""Login, last-seen, page-view, and mutation tracking for staff productivity."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import has_request_context, request
from sqlalchemy import func, select

from ..extensions import db
from ..models import User, UserActivityEvent
from ._admin_users_service import ApiError, _iso, _require_admin
from ._perms import CurrentUser
from ..permissions.applicant import applicant_only_user_id_subquery

EVENT_LOGIN = "login"
EVENT_LOGOUT = "logout"
EVENT_PAGE_VIEW = "page_view"
EVENT_API_WRITE = "api_write"

_LAST_SEEN_MIN_SECONDS = 60
_PAGE_VIEW_DEDUP_SECONDS = 120
_MAX_PATH = 500
_MAX_SUMMARY = 300
_MAX_UA = 500

_SKIP_WRITE_PREFIXES = (
    "/api/v1/me/activity",
    "/api/v1/admin/activity",
    "/api/v1/__debug",
    "/api/v1/auth/",
)

_WRITE_LABELS: tuple[tuple[str, str], ...] = (
    ("/api/v1/projects", "a project"),
    ("/api/v1/rfis", "an RFI"),
    ("/api/v1/submittals", "a submittal"),
    ("/api/submittals", "a submittal"),
    ("/api/v1/commitments", "a commitment / PO"),
    ("/api/purchase-orders", "a purchase order"),
    ("/api/v1/material-orders", "a material order"),
    ("/api/v1/pay-applications", "a pay application"),
    ("/api/v1/rfps", "an RFP"),
    ("/api/v1/rfp", "an RFP"),
    ("/api/v1/lead-estimates", "a lead estimate"),
    ("/api/v1/estimate-queue", "the estimate queue"),
    ("/api/v1/drawings", "a drawing"),
    ("/api/v1/documents", "a document"),
    ("/api/v1/issues", "an issue"),
    ("/api/v1/daily-reports", "a daily report"),
    ("/api/v1/daily-pretasks", "a pretask"),
    ("/api/v1/time-clock", "time clock"),
    ("/api/time", "time"),
    ("/api/v1/photos", "a photo"),
    ("/api/v1/safety", "safety"),
    ("/api/v1/hr/", "HR"),
    ("/api/v1/hrms", "HRMS"),
    ("/api/v1/admin/users", "a user account"),
    ("/api/v1/admin/roles", "a role"),
    ("/api/v1/playbooks", "a playbook"),
    ("/api/v1/companies", "a company"),
    ("/api/v1/contacts", "a contact"),
    ("/api/v1/calendar-events", "a calendar event"),
    ("/api/v1/ap/", "AP / invoices"),
    ("/api/v1/ingest", "ingest"),
    ("/api/v1/correspondence", "correspondence"),
    ("/api/workflows", "a workflow"),
    ("/api/ai", "AI"),
    ("/api/v1/ai", "AI"),
)

_WRITE_VERBS = {
    "POST": "Created or submitted",
    "PATCH": "Updated",
    "PUT": "Updated",
    "DELETE": "Deleted",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def client_ip() -> str | None:
    if not has_request_context():
        return None
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first[:45]
    if request.remote_addr:
        return str(request.remote_addr)[:45]
    return None


def client_user_agent() -> str | None:
    if not has_request_context():
        return None
    ua = (request.headers.get("User-Agent") or "").strip()
    return ua[:_MAX_UA] or None


def _clip(value: str | None, n: int) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    return s[:n]


def _write_summary(method: str, path: str) -> str:
    verb = _WRITE_VERBS.get(method.upper(), method.upper())
    p = (path or "").split("?")[0]
    for prefix, noun in _WRITE_LABELS:
        if p.startswith(prefix):
            return f"{verb} {noun}"[:_MAX_SUMMARY]
    short = p or "/"
    if len(short) > 80:
        short = short[:77] + "..."
    return f"{verb} {short}"[:_MAX_SUMMARY]


def _page_summary(path: str, title: str | None) -> str:
    raw = (path or "").split("?")[0].rstrip("/")
    name = raw.rsplit("/", 1)[-1] if raw else ""
    name = name.replace(".html", "").replace("-", " ").replace("_", " ").strip()
    if name and name.lower() not in {"index", "usis"}:
        label = " ".join(part.capitalize() for part in name.split())
    else:
        t = (title or "").strip()
        label = t if t and t.upper() != "USIS" else (raw or "a page")
    return f"Opened {label}"[:_MAX_SUMMARY]


def _add_event(
    user: User,
    *,
    event_type: str,
    summary: str,
    source: str | None = None,
    method: str | None = None,
    path: str | None = None,
    extra: dict[str, Any] | None = None,
) -> UserActivityEvent:
    row = UserActivityEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        event_type=event_type,
        source=_clip(source, 32),
        method=_clip(method, 10),
        path=_clip(path, _MAX_PATH),
        summary=summary[:_MAX_SUMMARY],
        ip_address=client_ip(),
        user_agent=client_user_agent(),
        extra=extra,
        created_at=_now(),
    )
    db.session.add(row)
    return row


def touch_last_seen(user: User, *, force: bool = False) -> bool:
    now = _now()
    prev = _aware(user.last_seen_at)
    if not force and prev is not None and (now - prev).total_seconds() < _LAST_SEEN_MIN_SECONDS:
        return False
    user.last_seen_at = now
    return True


def record_login(user: User, source: str) -> None:
    now = _now()
    user.last_login_at = now
    user.last_seen_at = now
    db.session.add(user)
    _add_event(
        user,
        event_type=EVENT_LOGIN,
        source=source,
        path="/auth/login" if source != "mobile" else "/api/v1/auth/mobile/login",
        method="POST",
        summary=f"Signed in ({source})",
    )


def record_logout(user: User) -> None:
    touch_last_seen(user, force=True)
    _add_event(
        user,
        event_type=EVENT_LOGOUT,
        source="web",
        path="/auth/logout",
        method="GET",
        summary="Signed out",
    )


def record_page_view(user: User, path: str, title: str | None = None) -> UserActivityEvent | None:
    clean = _clip(path, _MAX_PATH) or "/"
    now = _now()
    cutoff = now - timedelta(seconds=_PAGE_VIEW_DEDUP_SECONDS)
    recent = db.session.scalar(
        select(UserActivityEvent.id)
        .where(
            UserActivityEvent.user_id == user.id,
            UserActivityEvent.event_type == EVENT_PAGE_VIEW,
            UserActivityEvent.path == clean,
            UserActivityEvent.created_at >= cutoff,
        )
        .limit(1)
    )
    touch_last_seen(user, force=True)
    if recent is not None:
        return None
    extra = {"title": (title or "").strip()[:200]} if (title or "").strip() else None
    return _add_event(
        user,
        event_type=EVENT_PAGE_VIEW,
        source="web",
        method="GET",
        path=clean,
        summary=_page_summary(clean, title),
        extra=extra,
    )


def should_skip_api_write(path: str) -> bool:
    p = (path or "").rstrip("/") or path
    for prefix in _SKIP_WRITE_PREFIXES:
        if p.startswith(prefix):
            return True
    return False


def record_api_write(user: User, method: str, path: str, status: int) -> UserActivityEvent | None:
    clean = _clip(path, _MAX_PATH) or "/"
    if should_skip_api_write(clean):
        return None
    touch_last_seen(user, force=True)
    return _add_event(
        user,
        event_type=EVENT_API_WRITE,
        source="api",
        method=(method or "").upper()[:10] or None,
        path=clean,
        summary=_write_summary(method, clean),
        extra={"status": status},
    )


def after_request_track(response) -> None:
    """Best-effort last-seen + mutation log. Never raises to the caller."""
    from ._perms import current_user

    if request.method == "OPTIONS":
        return
    path = request.path or ""
    if not (
        path.startswith("/api/v1")
        or path.startswith("/api/ai")
        or path.startswith("/api/submittals")
        or path.startswith("/api/workflows")
        or path.startswith("/api/purchase-orders")
        or path.startswith("/api/correspondence")
    ):
        return
    cu = current_user()
    user = cu.user
    if user is None or getattr(user, "id", None) is None:
        return
    status = int(getattr(response, "status_code", 0) or 0)
    if status < 200 or status >= 400:
        return
    method = (request.method or "").upper()
    dirty = False
    if method in ("POST", "PUT", "PATCH", "DELETE"):
        if record_api_write(user, method, path, status) is not None:
            dirty = True
        else:
            dirty = touch_last_seen(user) or dirty
    else:
        dirty = touch_last_seen(user)
    if dirty:
        db.session.commit()


def record_page_view_for_current(cu: CurrentUser, data: dict[str, Any] | None) -> dict[str, Any]:
    if cu.user is None:
        raise ApiError("authentication required", 401)
    if not isinstance(data, dict):
        raise ApiError("JSON body required", 400)
    path = str(data.get("path") or data.get("page") or "").strip()
    if not path:
        raise ApiError("path is required", 400)
    title = data.get("title")
    title_s = None if title is None else str(title).strip()[:200]
    row = record_page_view(cu.user, path, title_s)
    db.session.commit()
    return {"ok": True, "recorded": row is not None, "entity": "user_activity"}


def _event_public(row: UserActivityEvent, user: User | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "event_type": row.event_type,
        "source": row.source,
        "method": row.method,
        "path": row.path,
        "summary": row.summary,
        "created_at": _iso(row.created_at),
    }
    if user is not None:
        name = " ".join(x for x in (user.first_name, user.last_name) if x).strip()
        out["user_name"] = name or user.email
        out["user_email"] = user.email
    return out


def list_events(
    cu: CurrentUser,
    *,
    user_id: uuid.UUID | None = None,
    event_type: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    _require_admin(cu)
    stmt = select(UserActivityEvent)
    count_stmt = select(func.count()).select_from(UserActivityEvent)
    if user_id is not None:
        stmt = stmt.where(UserActivityEvent.user_id == user_id)
        count_stmt = count_stmt.where(UserActivityEvent.user_id == user_id)
    if event_type:
        stmt = stmt.where(UserActivityEvent.event_type == event_type)
        count_stmt = count_stmt.where(UserActivityEvent.event_type == event_type)
    if since is not None:
        stmt = stmt.where(UserActivityEvent.created_at >= since)
        count_stmt = count_stmt.where(UserActivityEvent.created_at >= since)
    total = int(db.session.scalar(count_stmt) or 0)
    rows = db.session.scalars(
        stmt.order_by(UserActivityEvent.created_at.desc()).offset(offset).limit(limit)
    ).all()
    user_ids = {r.user_id for r in rows}
    users: dict[uuid.UUID, User] = {}
    if user_ids:
        for u in db.session.scalars(select(User).where(User.id.in_(user_ids))).all():
            users[u.id] = u
    return [_event_public(r, users.get(r.user_id)) for r in rows], total


def activity_summary(cu: CurrentUser, *, days: int = 7) -> dict[str, Any]:
    _require_admin(cu)
    days = max(1, min(int(days), 90))
    now = _now()
    since = now - timedelta(days=days)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    users = db.session.scalars(
        select(User)
        .where(User.is_active.is_(True), User.id.notin_(applicant_only_user_id_subquery()))
        .order_by(User.last_seen_at.desc().nullslast(), User.email.asc())
    ).all()

    counts_period = dict(
        db.session.execute(
            select(UserActivityEvent.user_id, func.count())
            .where(UserActivityEvent.created_at >= since)
            .group_by(UserActivityEvent.user_id)
        ).all()
    )
    counts_today = dict(
        db.session.execute(
            select(UserActivityEvent.user_id, func.count())
            .where(UserActivityEvent.created_at >= today_start)
            .group_by(UserActivityEvent.user_id)
        ).all()
    )
    login_counts = dict(
        db.session.execute(
            select(UserActivityEvent.user_id, func.count())
            .where(
                UserActivityEvent.created_at >= since,
                UserActivityEvent.event_type == EVENT_LOGIN,
            )
            .group_by(UserActivityEvent.user_id)
        ).all()
    )

    items: list[dict[str, Any]] = []
    for u in users:
        name = " ".join(x for x in (u.first_name, u.last_name) if x).strip()
        items.append(
            {
                "id": str(u.id),
                "email": u.email,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "name": name or u.email,
                "last_login_at": _iso(u.last_login_at),
                "last_seen_at": _iso(u.last_seen_at),
                "actions_today": int(counts_today.get(u.id) or 0),
                "actions_period": int(counts_period.get(u.id) or 0),
                "logins_period": int(login_counts.get(u.id) or 0),
            }
        )
    return {
        "entity": "user_activity_summary",
        "days": days,
        "since": _iso(since),
        "items": items,
    }


def _parse_user_id(raw: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(raw).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def _err(exc: ApiError):
    from flask import jsonify

    return jsonify({"error": exc.message}), exc.status


def register_activity_routes(bp) -> None:
    from flask import jsonify, request as req

    from ._perms import current_user

    @bp.post("/me/activity/page-view")
    def post_me_page_view():
        body = req.get_json(silent=True) or {}
        try:
            return jsonify(record_page_view_for_current(current_user(), body))
        except ApiError as exc:
            return _err(exc)

    @bp.get("/admin/activity")
    def admin_list_activity():
        raw_uid = (req.args.get("user_id") or "").strip()
        uid = _parse_user_id(raw_uid) if raw_uid else None
        if raw_uid and uid is None:
            return jsonify({"error": "invalid user id"}), 400
        event_type = (req.args.get("event_type") or "").strip() or None
        allowed = {EVENT_LOGIN, EVENT_LOGOUT, EVENT_PAGE_VIEW, EVENT_API_WRITE}
        if event_type and event_type not in allowed:
            return jsonify({"error": "invalid event_type"}), 400
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
                user_id=uid,
                event_type=event_type,
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
                "entity": "user_activity",
            }
        )

    @bp.get("/admin/activity/summary")
    def admin_activity_summary():
        try:
            days = max(1, min(int(req.args.get("days") or 7), 90))
        except ValueError:
            return jsonify({"error": "invalid days"}), 400
        try:
            return jsonify(activity_summary(current_user(), days=days))
        except ApiError as exc:
            return _err(exc)
