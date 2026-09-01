"""Staff-to-staff 1:1 messenger (conversations + messages)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request
from sqlalchemy import and_, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from ..extensions import db
from ..models import User
from ..models.chat import ChatConversation, ChatMessage, ChatParticipant
from ._in_app_notifications import create_in_app_notification
from ._perms import CurrentUser, current_user, users_for_picker

MAX_BODY = 4000
MAX_MESSAGES = 200


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


def _parse_uuid(raw: str | None) -> uuid.UUID | None:
    if not raw or not str(raw).strip():
        return None
    try:
        return uuid.UUID(str(raw).strip())
    except ValueError:
        return None


def _display_name(u: User | None) -> str:
    if u is None:
        return "Unknown"
    name = " ".join(p for p in (u.first_name, u.last_name) if p).strip()
    if name:
        return name
    if u.username:
        return u.username
    return u.email or "User"


def _user_public(u: User | None) -> dict[str, Any]:
    if u is None:
        return {"id": None, "name": "Unknown", "email": ""}
    return {
        "id": str(u.id),
        "name": _display_name(u),
        "email": u.email or "",
    }


def _pair_key(a: uuid.UUID, b: uuid.UUID) -> str:
    left, right = sorted((str(a), str(b)))
    return f"{left}:{right}"


def _message_public(row: ChatMessage, *, me: uuid.UUID) -> dict[str, Any]:
    sender = row.sender
    return {
        "id": str(row.id),
        "conversation_id": str(row.conversation_id),
        "sender_id": str(row.sender_id) if row.sender_id else None,
        "sender": _user_public(sender),
        "body": row.body or "",
        "mine": bool(row.sender_id == me),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _participant_for(conv: ChatConversation, user_id: uuid.UUID) -> ChatParticipant | None:
    for p in conv.participants:
        if p.user_id == user_id:
            return p
    return None


def _other_participant(conv: ChatConversation, me: uuid.UUID) -> ChatParticipant | None:
    for p in conv.participants:
        if p.user_id != me:
            return p
    return None


def _unread_count(conv_id: uuid.UUID, me: uuid.UUID, last_read_at: datetime | None) -> int:
    q = select(func.count()).select_from(ChatMessage).where(
        ChatMessage.conversation_id == conv_id,
        ChatMessage.sender_id != me,
    )
    if last_read_at is not None:
        q = q.where(ChatMessage.created_at > last_read_at)
    return int(db.session.scalar(q) or 0)


def _last_message(conv_id: uuid.UUID) -> ChatMessage | None:
    return db.session.scalars(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(1)
    ).first()


def _conversation_public(conv: ChatConversation, *, me: uuid.UUID) -> dict[str, Any]:
    mine = _participant_for(conv, me)
    other = _other_participant(conv, me)
    other_user = other.user if other is not None else None
    last = _last_message(conv.id)
    unread = _unread_count(conv.id, me, mine.last_read_at if mine else None)
    last_pub = None
    if last is not None:
        last_pub = {
            "id": str(last.id),
            "body": last.body or "",
            "sender_id": str(last.sender_id) if last.sender_id else None,
            "created_at": last.created_at.isoformat() if last.created_at else None,
        }
    return {
        "id": str(conv.id),
        "other": _user_public(other_user),
        "last_message": last_pub,
        "unread": unread,
        "updated_at": (conv.last_message_at or conv.updated_at).isoformat()
        if (conv.last_message_at or conv.updated_at)
        else None,
    }


def _load_conversation(conv_id: uuid.UUID, me: uuid.UUID) -> ChatConversation:
    conv = db.session.scalars(
        select(ChatConversation)
        .where(ChatConversation.id == conv_id)
        .options(selectinload(ChatConversation.participants).joinedload(ChatParticipant.user))
    ).first()
    if conv is None:
        raise ApiError("conversation not found", 404)
    if _participant_for(conv, me) is None:
        raise ApiError("conversation not found", 404)
    return conv


def list_people(cu: CurrentUser, *, q: str = "", limit: int = 40) -> dict[str, Any]:
    me = _require_user(cu)
    n = max(1, min(int(limit or 40), 100))
    needle = (q or "").strip().lower()
    users = [u for u in users_for_picker() if u.id != me]
    if needle:
        users = [
            u
            for u in users
            if needle in _display_name(u).lower()
            or (u.email and needle in u.email.lower())
            or (u.username and needle in u.username.lower())
        ]
    return {
        "items": [_user_public(u) for u in users[:n]],
        "entity": "chat_users",
    }


def list_conversations(cu: CurrentUser) -> dict[str, Any]:
    me = _require_user(cu)
    convs = db.session.scalars(
        select(ChatConversation)
        .join(ChatParticipant, ChatParticipant.conversation_id == ChatConversation.id)
        .where(ChatParticipant.user_id == me)
        .options(selectinload(ChatConversation.participants).joinedload(ChatParticipant.user))
        .order_by(
            ChatConversation.last_message_at.desc().nullslast(),
            ChatConversation.updated_at.desc(),
        )
    ).unique().all()
    items = [_conversation_public(c, me=me) for c in convs]
    unread = sum(int(i.get("unread") or 0) for i in items)
    return {"items": items, "unread": unread, "entity": "chat_conversations"}


def unread_total(cu: CurrentUser) -> dict[str, Any]:
    me = _require_user(cu)
    mine = select(ChatParticipant).where(ChatParticipant.user_id == me)
    parts = db.session.scalars(mine).all()
    total = 0
    for p in parts:
        total += _unread_count(p.conversation_id, me, p.last_read_at)
    return {"unread": total, "entity": "chat"}


def get_or_create_conversation(cu: CurrentUser, other_user_id: uuid.UUID) -> dict[str, Any]:
    me = _require_user(cu)
    if other_user_id == me:
        raise ApiError("cannot message yourself", 400)
    other = db.session.get(User, other_user_id)
    if other is None or not other.is_active:
        raise ApiError("user not found", 404)
    key = _pair_key(me, other_user_id)
    conv = db.session.scalars(
        select(ChatConversation).where(ChatConversation.pair_key == key)
    ).first()
    if conv is None:
        conv = ChatConversation(pair_key=key)
        db.session.add(conv)
        try:
            db.session.flush()
        except IntegrityError:
            db.session.rollback()
            conv = db.session.scalars(
                select(ChatConversation).where(ChatConversation.pair_key == key)
            ).first()
            if conv is None:
                raise ApiError("could not open conversation", 500)
        else:
            db.session.add(ChatParticipant(conversation_id=conv.id, user_id=me))
            db.session.add(ChatParticipant(conversation_id=conv.id, user_id=other_user_id))
            db.session.flush()
    db.session.commit()
    conv = db.session.scalars(
        select(ChatConversation)
        .where(ChatConversation.id == conv.id)
        .options(selectinload(ChatConversation.participants).joinedload(ChatParticipant.user))
    ).first()
    assert conv is not None
    return {"item": _conversation_public(conv, me=me), "entity": "chat_conversations"}


def list_messages(
    cu: CurrentUser,
    conversation_id: uuid.UUID,
    *,
    after: uuid.UUID | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    me = _require_user(cu)
    conv = _load_conversation(conversation_id, me)
    n = max(1, min(int(limit or 100), MAX_MESSAGES))
    q = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conv.id)
        .options(joinedload(ChatMessage.sender))
        .order_by(ChatMessage.created_at.asc())
    )
    if after is not None:
        after_row = db.session.get(ChatMessage, after)
        if after_row is not None and after_row.conversation_id == conv.id and after_row.created_at:
            q = q.where(
                or_(
                    ChatMessage.created_at > after_row.created_at,
                    and_(
                        ChatMessage.created_at == after_row.created_at,
                        ChatMessage.id > after_row.id,
                    ),
                )
            )
    rows = db.session.scalars(q).all()
    if after is None and len(rows) > n:
        rows = rows[-n:]
    elif after is not None:
        rows = rows[:n]
    return {
        "items": [_message_public(r, me=me) for r in rows],
        "conversation": _conversation_public(conv, me=me),
        "entity": "chat_messages",
    }


def send_message(cu: CurrentUser, conversation_id: uuid.UUID, body: str) -> dict[str, Any]:
    me = _require_user(cu)
    text = (body or "").strip()
    if not text:
        raise ApiError("message is empty", 400)
    if len(text) > MAX_BODY:
        raise ApiError(f"message is too long (max {MAX_BODY} characters)", 400)
    conv = _load_conversation(conversation_id, me)
    now = _utcnow()
    row = ChatMessage(conversation_id=conv.id, sender_id=me, body=text)
    db.session.add(row)
    conv.last_message_at = now
    mine = _participant_for(conv, me)
    if mine is not None:
        mine.last_read_at = now
    db.session.flush()
    sender = cu.user
    other = _other_participant(conv, me)
    if other is not None:
        preview = text if len(text) <= 160 else text[:157] + "..."
        create_in_app_notification(
            user_id=other.user_id,
            title=f"Message from {_display_name(sender)}",
            body=preview,
            url=f"/usis-messenger.html?c={conv.id}",
        )
    db.session.commit()
    row = db.session.scalars(
        select(ChatMessage).where(ChatMessage.id == row.id).options(joinedload(ChatMessage.sender))
    ).first()
    assert row is not None
    return {"item": _message_public(row, me=me), "entity": "chat_messages"}


def mark_read(cu: CurrentUser, conversation_id: uuid.UUID) -> dict[str, Any]:
    me = _require_user(cu)
    conv = _load_conversation(conversation_id, me)
    mine = _participant_for(conv, me)
    if mine is not None:
        mine.last_read_at = _utcnow()
        db.session.flush()
        db.session.commit()
    return {"item": _conversation_public(conv, me=me), "entity": "chat_conversations"}


bp = Blueprint("messenger", __name__)


def _err(exc: ApiError):
    return jsonify({"error": exc.message, "entity": "chat"}), exc.status


@bp.get("/api/v1/me/chat/users")
def list_chat_users_route():
    try:
        q = (request.args.get("q") or "").strip()
        limit = request.args.get("limit") or 40
        return jsonify(list_people(current_user(), q=q, limit=int(limit)))
    except ApiError as exc:
        return _err(exc)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit", "entity": "chat"}), 400


@bp.get("/api/v1/me/chat/conversations")
def list_conversations_route():
    try:
        return jsonify(list_conversations(current_user()))
    except ApiError as exc:
        return _err(exc)


@bp.get("/api/v1/me/chat/unread-count")
def unread_count_route():
    try:
        return jsonify(unread_total(current_user()))
    except ApiError as exc:
        return _err(exc)


@bp.post("/api/v1/me/chat/conversations")
def create_conversation_route():
    data = request.get_json(silent=True) or {}
    other = _parse_uuid(str(data.get("user_id") or data.get("to_user_id") or ""))
    if other is None:
        return jsonify({"error": "user_id is required", "entity": "chat"}), 400
    try:
        return jsonify(get_or_create_conversation(current_user(), other))
    except ApiError as exc:
        return _err(exc)


@bp.get("/api/v1/me/chat/conversations/<conversation_id>/messages")
def list_messages_route(conversation_id: str):
    cid = _parse_uuid(conversation_id)
    if cid is None:
        return jsonify({"error": "invalid conversation id", "entity": "chat"}), 400
    after = _parse_uuid(request.args.get("after"))
    try:
        limit = int(request.args.get("limit") or 100)
        return jsonify(list_messages(current_user(), cid, after=after, limit=limit))
    except ApiError as exc:
        return _err(exc)
    except (TypeError, ValueError):
        return jsonify({"error": "invalid limit", "entity": "chat"}), 400


@bp.post("/api/v1/me/chat/conversations/<conversation_id>/messages")
def send_message_route(conversation_id: str):
    cid = _parse_uuid(conversation_id)
    if cid is None:
        return jsonify({"error": "invalid conversation id", "entity": "chat"}), 400
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(send_message(current_user(), cid, str(data.get("body") or "")))
    except ApiError as exc:
        return _err(exc)


@bp.post("/api/v1/me/chat/conversations/<conversation_id>/read")
def mark_read_route(conversation_id: str):
    cid = _parse_uuid(conversation_id)
    if cid is None:
        return jsonify({"error": "invalid conversation id", "entity": "chat"}), 400
    try:
        return jsonify(mark_read(current_user(), cid))
    except ApiError as exc:
        return _err(exc)


def register_on_app(app) -> None:
    if "messenger" not in app.blueprints:
        app.register_blueprint(bp)
