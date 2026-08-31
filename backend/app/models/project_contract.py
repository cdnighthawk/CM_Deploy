"""Owner/prime contracts on a project — one owner, several contracts per job."""
from __future__ import annotations

import uuid
from datetime import date
from typing import Optional

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class ProjectContract(UUIDPKMixin, TimestampMixin, db.Model):
    """A named owner contract on a project. One row may be the billing primary."""

    __tablename__ = "project_contracts"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contract_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="Prime contract")
    contract_value: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    contract_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    substantial_completion_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closeout_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    retention_percentage: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    contract_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    status_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    project = relationship("Project", back_populates="contracts")
