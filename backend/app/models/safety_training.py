"""Safety-owned training / certification records (Plan 7, Plan 19 read-through on HR employee page)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .document import Document
    from .project import Project


class SafetyTrainingRecord(UUIDPKMixin, TimestampMixin, db.Model):
    """Regulatory / site certifications (OSHA, forklift, First Aid, etc.) — Safety canonical store."""

    __tablename__ = "safety_training_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    training_type: Mapped[str] = mapped_column(String(80), nullable=False)
    credential_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    issuing_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    project: Mapped[Optional["Project"]] = relationship(foreign_keys=[project_id])
    document: Mapped[Optional["Document"]] = relationship(foreign_keys=[document_id])
