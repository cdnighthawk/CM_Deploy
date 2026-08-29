"""Persist Grok chats per signed-in user."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, inspect, select
from sqlalchemy.exc import ProgrammingError

from ..api._perms import CurrentUser
from ..extensions import db
from ..models.ai_chat import AiChatMessage, AiChatSession

MAX_SESSIONS_LIST = 40
MAX_TITLE = 80


def _tables_ready() -> bool:
    try:
        return inspect(db.session.get_bind()).has_table("ai_chat_sessions")
    except Exception:
        return False


def _uid(cu: CurrentUser) -> uuid.UUID | None:
    return cu.id if cu and cu.user is not None else None


def slim_attachments(atts: Any) -> list[dict[str, str]] | None:
    if not isinstance(atts, list) or not atts:
        return None
    out: list[dict[str, str]] = []
    for a in atts:
        if not isinstance(a, dict):
            continue
        row: dict[str, str] = {}
        if a.get("kind"):
            row["kind"] = str(a.get("kind"))
        if a.get("name"):
            row["name"] = str(a.get("name"))[:200]
        if a.get("url"):
            row["url"] = str(a.get("url"))[:2000]
        if row:
            out.append(row)
    return out or None


def _title_from_text(text: str) -> str:
    t = " ".join((text or "").split())
    if not t:
        return "New chat"
    return t[:MAX_TITLE]


def _session_public(row: AiChatSession, *, message_count: int | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "title": row.title,
        "mode": row.mode,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
    if message_count is not None:
        out["message_count"] = message_count
    return out


def _message_public(row: AiChatMessage) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "role": row.role,
        "content": row.content or "",
    }
    if row.attachments:
        out["attachments"] = row.attachments
    return out


def list_sessions(cu: CurrentUser, *, limit: int = MAX_SESSIONS_LIST) -> dict[str, Any]:
    user_id = _uid(cu)
    if user_id is None or not _tables_ready():
        return {"persisted": False, "items": []}
    rows = db.session.scalars(
        select(AiChatSession)
        .where(AiChatSession.user_id == user_id)
        .order_by(AiChatSession.updated_at.desc())
        .limit(max(1, min(limit, 80)))
    ).all()
    return {"persisted": True, "items": [_session_public(r) for r in rows]}


def get_session(cu: CurrentUser, session_id: str) -> dict[str, Any] | None:
    user_id = _uid(cu)
    if user_id is None or not _tables_ready():
        return None
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return None
    row = db.session.scalar(
        select(AiChatSession).where(AiChatSession.id == sid, AiChatSession.user_id == user_id)
    )
    if row is None:
        return None
    msgs = db.session.scalars(
        select(AiChatMessage)
        .where(AiChatMessage.session_id == row.id)
        .order_by(AiChatMessage.sort_index.asc(), AiChatMessage.created_at.asc())
    ).all()
    return {
        "persisted": True,
        **_session_public(row, message_count=len(msgs)),
        "messages": [_message_public(m) for m in msgs],
    }


def create_session(
    cu: CurrentUser,
    *,
    title: str | None = None,
    mode: str | None = None,
    messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    user_id = _uid(cu)
    if user_id is None or not _tables_ready():
        return None
    row = AiChatSession(
        user_id=user_id,
        title=_title_from_text(title or "") or "New chat",
        mode=(mode or "").strip() or None,
    )
    try:
        db.session.add(row)
        db.session.flush()
        if messages:
            _append_messages(row, messages)
            if row.title == "New chat":
                first_user = next((m for m in messages if m.get("role") == "user" and m.get("content")), None)
                if first_user:
                    row.title = _title_from_text(str(first_user.get("content") or ""))
        db.session.commit()
    except ProgrammingError:
        db.session.rollback()
        return None
    return get_session(cu, str(row.id))


def delete_session(cu: CurrentUser, session_id: str) -> bool:
    user_id = _uid(cu)
    if user_id is None or not _tables_ready():
        return False
    try:
        sid = uuid.UUID(str(session_id))
    except ValueError:
        return False
    row = db.session.scalar(
        select(AiChatSession).where(AiChatSession.id == sid, AiChatSession.user_id == user_id)
    )
    if row is None:
        return False
    db.session.delete(row)
    db.session.commit()
    return True


def _append_messages(session: AiChatSession, messages: list[dict[str, Any]]) -> None:
    start = db.session.scalar(
        select(func.coalesce(func.max(AiChatMessage.sort_index), -1)).where(
            AiChatMessage.session_id == session.id
        )
    )
    idx = int(start) + 1
    for m in messages:
        if not isinstance(m, dict):
            continue
        role = str(m.get("role") or "").strip().lower()
        if role not in ("user", "assistant"):
            continue
        content = m.get("content")
        if content is None:
            content = ""
        if not isinstance(content, str):
            content = str(content)
        atts = slim_attachments(m.get("attachments"))
        db.session.add(
            AiChatMessage(
                session_id=session.id,
                role=role,
                content=content,
                attachments=atts,
                sort_index=idx,
            )
        )
        idx += 1


def append_turn(
    cu: CurrentUser,
    *,
    session_id: str | None,
    mode: str | None,
    user_message: dict[str, Any],
    assistant_message: dict[str, Any],
) -> str | None:
    """Save one user+assistant pair. Returns session id or None if not signed in."""
    user_id = _uid(cu)
    if user_id is None or not _tables_ready():
        return None
    try:
        return _append_turn_inner(user_id, session_id, mode, user_message, assistant_message)
    except ProgrammingError:
        db.session.rollback()
        return None


def can_persist(cu: CurrentUser) -> bool:
    return _uid(cu) is not None and _tables_ready()


def _append_turn_inner(
    user_id: uuid.UUID,
    session_id: str | None,
    mode: str | None,
    user_message: dict[str, Any],
    assistant_message: dict[str, Any],
) -> str:
    row = None
    if session_id:
        try:
            sid = uuid.UUID(str(session_id))
        except ValueError:
            sid = None
        if sid:
            row = db.session.scalar(
                select(AiChatSession).where(AiChatSession.id == sid, AiChatSession.user_id == user_id)
            )
    if row is None:
        title = _title_from_text(str(user_message.get("content") or ""))
        row = AiChatSession(user_id=user_id, title=title, mode=(mode or "").strip() or None)
        db.session.add(row)
        db.session.flush()
    elif row.title == "New chat":
        row.title = _title_from_text(str(user_message.get("content") or "")) or row.title
    if mode:
        row.mode = str(mode).strip() or row.mode
    _append_messages(row, [user_message, assistant_message])
    row.updated_at = datetime.now(tz=timezone.utc)
    db.session.commit()
    return str(row.id)
