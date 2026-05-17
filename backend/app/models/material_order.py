"""Project material purchase orders — vendor-grouped tracking linked to PO commitments."""
from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .commitment import Commitment
    from .company import Company
    from .project import Project


class ProjectMaterialOrder(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "project_material_orders"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    vendor_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )
    vendor_name: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    order_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    lead_time_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    schedule_anchor_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expected_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    shipping_company: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    project: Mapped["Project"] = relationship(foreign_keys=[project_id])
    commitment: Mapped["Commitment"] = relationship(foreign_keys=[commitment_id])
    vendor_company: Mapped[Optional["Company"]] = relationship(foreign_keys=[vendor_company_id])
