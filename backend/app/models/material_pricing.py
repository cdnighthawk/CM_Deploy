"""Manufacturer material list pricing (multi-vendor catalog rows)."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from sqlalchemy import Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class MaterialPrice(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "material_pricing"
    __table_args__ = (
        UniqueConstraint("manufacturer", "item", name="uq_material_pricing_manufacturer_item"),
    )

    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    item: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    csi_spec_section: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mounting_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    labor_per: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'USD'")
    )
    unit_of_measure: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'EA'")
    )
