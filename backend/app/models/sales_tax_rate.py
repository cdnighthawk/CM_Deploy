"""California CDTFA (and future) sales and use tax reference rates."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import text

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class SalesTaxRate(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "sales_tax_rates"
    __table_args__ = (
        UniqueConstraint(
            "state",
            "location",
            "type",
            name="uq_sales_tax_rates_state_location_type",
        ),
    )

    state: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
        index=True,
        server_default=text("'CA'"),
    )
    location: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    county: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'CDTFA'"),
    )
