"""AGC San Diego / Golden State Planroom weekly listing rows."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class GoldenStatePlanroomLead(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "golden_state_planroom_leads"

    plan_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    bid_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    bid_time: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    addenda_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    estimate_high: Mapped[Optional[Decimal]] = mapped_column(Numeric(16, 2), nullable=True)
    is_new: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    bid_date_changed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    listing_week: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    source_file: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(60), nullable=False, default="ONLINE_PLAN_SERVICE", server_default="ONLINE_PLAN_SERVICE"
    )
    crm_stage: Mapped[str] = mapped_column(
        String(80), nullable=False, default="New Lead", server_default="New Lead", index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    project_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    detail: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    details_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_row: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
