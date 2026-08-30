"""Formal estimate headers and lines (Plan 4) — now a first-class job estimate.

Each lead can have many independent estimates (different GCs, drawing sets,
or post-award revisions). Takeoff lines belong to an Estimate.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .company import Company
    from .drawing_set import DrawingSet
    from .lead_estimate import LeadEstimate
    from .takeoff_line_item import TakeoffLineItem


class Estimate(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimates"

    lead_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="CASCADE"),
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
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", server_default="draft")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bid_location: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    total: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="Target due date for this estimate version"
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Original Estimate",
        server_default="Original Estimate",
    )
    version_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    gc_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gc_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    drawing_set_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawing_sets.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    fee_percentage: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    profit_margin: Mapped[Optional[Decimal]] = mapped_column(Numeric(7, 4), nullable=True)
    rom: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    estimate_locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    lead_estimate: Mapped[Optional["LeadEstimate"]] = relationship(
        "LeadEstimate",
        back_populates="estimates",
        foreign_keys=[lead_estimate_id],
    )
    gc_company: Mapped[Optional["Company"]] = relationship("Company", foreign_keys=[gc_company_id])
    drawing_set: Mapped[Optional["DrawingSet"]] = relationship(
        "DrawingSet",
        back_populates="estimates",
        foreign_keys=[drawing_set_id],
    )
    created_from: Mapped[Optional["Estimate"]] = relationship(
        "Estimate",
        remote_side="Estimate.id",
        foreign_keys=[created_from_id],
        back_populates="revisions",
    )
    revisions: Mapped[List["Estimate"]] = relationship(
        "Estimate",
        foreign_keys=[created_from_id],
        back_populates="created_from",
    )
    created_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_id])
    takeoff_lines: Mapped[List["TakeoffLineItem"]] = relationship(
        "TakeoffLineItem",
        back_populates="estimate",
        cascade="all, delete-orphan",
        order_by="TakeoffLineItem.sort_order",
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
