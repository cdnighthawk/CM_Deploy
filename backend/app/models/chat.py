"""In-app 1:1 messenger (staff-to-staff chat)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .auth import User
from .base import TimestampMixin, UUIDPKMixin


class ChatConversation(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        UniqueConstraint("pair_key", name="uq_chat_conversations_pair_key"),
    )

    pair_key: Mapped[str] = mapped_column(String(80), nullable=False)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    participants: Mapped[List["ChatParticipant"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )
    messages: Mapped[List["ChatMessage"]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )


class ChatParticipant(TimestampMixin, db.Model):
    __tablename__ = "chat_participants"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    last_read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    conversation: Mapped[ChatConversation] = relationship(back_populates="participants")
    user: Mapped[User] = relationship("User", foreign_keys=[user_id])


class ChatMessage(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "chat_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")

    conversation: Mapped[ChatConversation] = relationship(back_populates="messages")
    sender: Mapped[Optional[User]] = relationship("User", foreign_keys=[sender_id])
