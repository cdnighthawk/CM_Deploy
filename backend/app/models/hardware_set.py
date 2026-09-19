"""Estimate-scoped hardware sets (08 71 00) — not the company HD-n library."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin, TenantMixin

if TYPE_CHECKING:
    from .estimate import Estimate
    from .material_pricing import MaterialPrice


HARDWARE_CATEGORIES = (
    "hinge",
    "pivot",
    "lockset",
    "exit_device",
    "closer",
    "stop",
    "kick_plate",
    "armor_plate",
    "push_pull",
    "flush_bolt",
    "coordinator",
    "threshold",
    "seal",
    "door_bottom",
    "silencer",
    "viewer",
    "overhead_stop",
    "holder",
    "position_switch",
    "power",
    "other",
)


class HardwareSet(UUIDPKMixin, TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "hardware_sets"
    __table_args__ = (
        UniqueConstraint("estimate_id", "set_no_normalized", name="uq_hardware_sets_estimate_set_no"),
    )

    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estimate: Mapped["Estimate"] = relationship("Estimate", foreign_keys=[estimate_id])

    set_no: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    set_no_normalized: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    governs: Mapped[str] = mapped_column(String(20), nullable=False, default="spec", server_default="spec")
    source_doc_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    finish_default: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    fire_required: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    pair_set: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    electrified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    conflicts: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    items: Mapped[list["HardwareSetItem"]] = relationship(
        "HardwareSetItem",
        back_populates="hardware_set",
        cascade="all, delete-orphan",
        order_by="HardwareSetItem.seq",
    )


class HardwareSetItem(UUIDPKMixin, TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "hardware_set_items"

    hardware_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hardware_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hardware_set: Mapped["HardwareSet"] = relationship("HardwareSet", back_populates="items")

    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    qty: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("1"))
    qty_unit: Mapped[str] = mapped_column(String(20), nullable=False, default="ea", server_default="ea")
    category: Mapped[str] = mapped_column(String(40), nullable=False, default="other", server_default="other")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    catalog: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    function: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    finish: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    alternates: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    material_pricing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("material_pricing.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    material_price: Mapped[Optional["MaterialPrice"]] = relationship(
        "MaterialPrice",
        foreign_keys=[material_pricing_id],
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
