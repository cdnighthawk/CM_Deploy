"""Reference prevailing wage rates by state, sub-area, year, and trade."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import Boolean, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class WageRate(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "wage_rates"
    __table_args__ = (
        UniqueConstraint(
            "state",
            "sub_area",
            "year",
            "trade",
            name="uq_wage_rates_state_sub_area_year_trade",
        ),
    )

    state: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    sub_area: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        server_default=sa.text("''"),
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    trade: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    basic_hourly_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    health_welfare: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    pension: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    vacation_holiday: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    other_payments: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    training: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_assumed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sa.false()
    )
