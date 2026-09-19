"""Agent heartbeats and ACCDocs/Forma status events from the Windows data server."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin, TenantMixin


class IngestAgentEvent(UUIDPKMixin, TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "ingest_agent_events"

    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="accdocs", index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    lead_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    folder_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    uploaded_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    host: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    detail: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
