"""Per-user Grok chat threads."""
from __future__ import annotations

import uuid
from typing import Any, List, Optional

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .auth import User
from .base import TimestampMixin, UUIDPKMixin


class AiChatSession(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "ai_chat_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False, default="New chat")
    mode: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])
    messages: Mapped[List["AiChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="AiChatMessage.sort_index",
    )


class AiChatMessage(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "ai_chat_messages"

    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attachments: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    sort_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    session: Mapped[AiChatSession] = relationship(back_populates="messages")
