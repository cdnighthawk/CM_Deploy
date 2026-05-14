"""Unified takeoff / estimate line items (Plan 3 — lead and/or project scoped)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class TakeoffLineItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "takeoff_line_items"

    lead_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    lead_estimate = relationship("LeadEstimate", back_populates="takeoff_lines")

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    section: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="EA", server_default="EA")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    extended_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    cost_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="M",
        server_default="M",
        comment="L labor, M material, E equipment, S subcontract, O other",
    )

    job_cost_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    job_cost_code_description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    job_cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="Reserved for normalized cost code FK"
    )

    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    measurement_data: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
