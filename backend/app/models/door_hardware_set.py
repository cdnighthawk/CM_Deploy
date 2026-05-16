"""Company hardware set templates for door schedule expansion."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .material_pricing import MaterialPrice


class DoorHardwareSet(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "door_hardware_sets"
    __table_args__ = (UniqueConstraint("code", name="uq_door_hardware_sets_code"),)

    code: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    items: Mapped[list["DoorHardwareSetItem"]] = relationship(
        "DoorHardwareSetItem",
        back_populates="hardware_set",
        cascade="all, delete-orphan",
        order_by="DoorHardwareSetItem.sort_order",
    )


class DoorHardwareSetItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "door_hardware_set_items"

    hardware_set_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("door_hardware_sets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hardware_set: Mapped["DoorHardwareSet"] = relationship("DoorHardwareSet", back_populates="items")

    label: Mapped[str] = mapped_column(String(255), nullable=False, default="", server_default="")
    cost_type: Mapped[str] = mapped_column(String(20), nullable=False, default="M", server_default="M")
    default_qty: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("1"))
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="EA", server_default="EA")
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
    default_unit_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
