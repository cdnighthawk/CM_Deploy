"""Header bell notifications (stored in ``hrms_notifications``)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify
from sqlalchemy import func, select

from ..extensions import db
from ..models import User
from ..models.hrms_core import HrmsNotification
from ._perms import CurrentUser, current_user


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        self.message = message
        self.status = status


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _require_user(cu: CurrentUser) -> uuid.UUID:
    if cu.user is None or cu.id is None:
        raise ApiError("sign in required", 401)
    return cu.id


def create_in_app_notification(
    *,
    user_id: uuid.UUID,
    title: str,
    body: str | None = None,
    url: str | None = None,
    channel: str = "in_app",
) -> HrmsNotification:
    row = HrmsNotification(
        user_id=user_id,
        channel=(channel or "in_app")[:32],
        title=(title or "Notice")[:255],
        body=body,
        payload={"url": url} if url else {},
    )
    db.session.add(row)
    db.session.flush()
    return row


def notify_user_by_email(
    *,
    email: str,
    title: str,
    body: str | None = None,
    url: str | None = None,
) -> HrmsNotification | None:
    address = (email or "").strip().lower()
    if not address:
        return None
    user = db.session.scalars(select(User).where(func.lower(User.email) == address)).first()
    if user is None:
        return None
    return create_in_app_notification(user_id=user.id, title=title, body=body, url=url)


def notification_public(row: HrmsNotification) -> dict[str, Any]:
    payload = row.payload if isinstance(row.payload, dict) else {}
    return {
        "id": str(row.id),
        "title": row.title,
        "body": row.body or "",
        "url": payload.get("url") or "",
        "channel": row.channel,
        "read": row.read_at is not None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def list_for_user(cu: CurrentUser, *, limit: int = 40) -> dict[str, Any]:
    uid = _require_user(cu)
    n = max(1, min(int(limit or 40), 100))
    rows = db.session.scalars(
        select(HrmsNotification)
        .where(HrmsNotification.user_id == uid)
        .order_by(HrmsNotification.created_at.desc())
        .limit(n)
    ).all()
    items = [notification_public(r) for r in rows]
    unread = sum(1 for i in items if not i["read"])
    return {"items": items, "unread": unread, "entity": "notifications"}


def mark_read(cu: CurrentUser, notification_id: uuid.UUID) -> dict[str, Any] | None:
    uid = _require_user(cu)
    row = db.session.get(HrmsNotification, notification_id)
    if row is None or row.user_id != uid:
        return None
    if row.read_at is None:
        row.read_at = _utcnow()
        db.session.flush()
        db.session.commit()
    return notification_public(row)


bp = Blueprint("in_app_notifications", __name__)


def _parse_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


@bp.get("/api/v1/me/notifications")
def list_my_notifications():
    try:
        return jsonify(list_for_user(current_user()))
    except ApiError as exc:
        return jsonify({"error": exc.message, "entity": "notifications"}), exc.status


@bp.post("/api/v1/me/notifications/<notification_id>/read")
def mark_my_notification_read(notification_id: str):
    nid = _parse_uuid(notification_id)
    if nid is None:
        return jsonify({"error": "invalid notification id", "entity": "notifications"}), 400
    try:
        item = mark_read(current_user(), nid)
    except ApiError as exc:
        return jsonify({"error": exc.message, "entity": "notifications"}), exc.status
    if item is None:
        return jsonify({"error": "not found", "entity": "notifications"}), 404
    return jsonify({"item": item, "entity": "notifications"})


def register_on_app(app) -> None:
    if "in_app_notifications" not in app.blueprints:
        app.register_blueprint(bp)
