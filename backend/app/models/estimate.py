"""Formal estimate headers and lines (Plan 4) — links to unified takeoff rows."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class Estimate(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimates"

    lead_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="Draft", server_default="Draft")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="Target due date for this estimate version"
    )

    line_items = relationship(
        "EstimateLineItem",
        back_populates="estimate",
        cascade="all, delete-orphan",
        order_by="EstimateLineItem.sort_order",
    )


class EstimateLineItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_line_items"

    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    takeoff_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("takeoff_line_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    markup_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    vendor_quote: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)

    estimate = relationship("Estimate", back_populates="line_items")
    takeoff_line_item = relationship("TakeoffLineItem")
