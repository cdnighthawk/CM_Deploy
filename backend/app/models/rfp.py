"""RFP core tables (Plan 5) — minimal vertical slice."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class Rfp(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfps"

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
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="Draft", server_default="Draft")
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    public_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    line_items: Mapped[List["RfpLineItem"]] = relationship(
        back_populates="rfp", cascade="all, delete-orphan", order_by="RfpLineItem.sort_order"
    )
    vendor_quotes: Mapped[List["RfpVendorQuote"]] = relationship(
        back_populates="rfp", cascade="all, delete-orphan"
    )


class RfpLineItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfp_line_items"

    rfp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="EA", server_default="EA")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rfp = relationship("Rfp", back_populates="line_items")


class RfpVendorQuote(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfp_vendor_quotes"

    rfp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_label: Mapped[str] = mapped_column(String(255), nullable=False, default="Vendor", server_default="Vendor")
    line_prices: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rfp = relationship("Rfp", back_populates="vendor_quotes")
