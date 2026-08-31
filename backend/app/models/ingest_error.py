"""Persisted failures from mass ingest, bearer ingest, and the folder script."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class IngestErrorEvent(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "ingest_error_events"

    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="mass_ingest", index=True)
    relative_path: Mapped[str] = mapped_column(Text, nullable=False, default="")
    filename: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="")
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    http_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actor_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
