"""Manufacturer material list pricing (multi-vendor catalog rows)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import text

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin, TenantMixin

if TYPE_CHECKING:
    from .company import Company


class MaterialPrice(UUIDPKMixin, TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "material_pricing"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "manufacturer",
            "item",
            name="uq_material_pricing_org_manufacturer_item",
        ),
    )

    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    item: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    csi_spec_section: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    mounting_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    labor_per: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    labor_units_per_hour: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    labor_rate_unit: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    size_width_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    size_height_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    size_depth_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'USD'")
    )
    unit_of_measure: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default=text("'EA'")
    )
    supplier_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    supplier_company: Mapped[Optional["Company"]] = relationship(
        foreign_keys=[supplier_company_id]
    )
