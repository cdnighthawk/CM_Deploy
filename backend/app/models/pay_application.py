"""Pay applications (G702-style) and schedule-of-values lines (G703 / Textura-style grid)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .project import Project

pay_application_status_enum = ENUM(
    "draft",
    "submitted",
    "certified",
    "paid",
    name="pay_application_status",
    create_type=False,
)


class PayApplication(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "pay_applications"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    application_number: Mapped[int] = mapped_column(Integer, nullable=False)
    period_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        pay_application_status_enum, nullable=False, default="draft", server_default="draft"
    )

    original_contract_sum: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    net_change_by_change_orders: Mapped[Decimal] = mapped_column(
        Numeric(15, 2), nullable=False, default=Decimal("0"), server_default="0"
    )
    contract_sum_to_date: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    total_completed_and_stored_to_date: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    retainage_total: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    total_earned_less_retainage: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    less_previous_certificates: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    current_payment_due: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    balance_to_finish_including_retainage: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)

    architect_certified_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    architect_certified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    textura_invoice_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    project: Mapped["Project"] = relationship("Project", back_populates="pay_applications")
    lines: Mapped[List["PayApplicationLine"]] = relationship(
        "PayApplicationLine",
        back_populates="pay_application",
        cascade="all, delete-orphan",
        order_by="PayApplicationLine.sort_order",
    )


class PayApplicationLine(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "pay_application_lines"

    pay_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pay_applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("pay_application_lines.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    phase_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    scheduled_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    net_change_co: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    work_from_previous: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    work_this_period: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    materials_stored: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    retention_to_date: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    balance_to_complete: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    balance_due: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    percent_complete: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    pay_application: Mapped["PayApplication"] = relationship("PayApplication", back_populates="lines")
