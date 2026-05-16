"""Audit log for Textura TPM sync runs."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class TexturaSyncLog(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "textura_sync_logs"

    direction: Mapped[str] = mapped_column(String(16), nullable=False, default="export")
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    loaded: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skipped: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_details: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, nullable=True)
    tpm_job_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
