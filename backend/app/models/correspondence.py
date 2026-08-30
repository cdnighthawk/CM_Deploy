"""Project correspondence archive — Graph mail/Teams persisted as files, not chat."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class CorrespondenceSource(UUIDPKMixin, TimestampMixin, db.Model):
    """Allow-listed mailbox or mapped Teams channel for Phase 1 ingest."""

    __tablename__ = "correspondence_sources"
    __table_args__ = (UniqueConstraint("source_type", "external_key", name="uq_correspondence_sources_type_key"),)

    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    external_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mailbox: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    team_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    channel_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    items: Mapped[list["CorrespondenceItem"]] = relationship(back_populates="source")


class CorrespondenceItem(UUIDPKMixin, TimestampMixin, db.Model):
    """One archived message or channel post as files + metadata."""

    __tablename__ = "correspondence_items"

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("correspondence_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, default="mailbox")
    graph_message_id: Mapped[Optional[str]] = mapped_column(String(512), nullable=True, unique=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    from_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    storage_relpath: Mapped[str] = mapped_column(String(1024), nullable=False)
    search_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_attachments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    attachment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    filed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    source: Mapped[Optional[CorrespondenceSource]] = relationship(back_populates="items")
