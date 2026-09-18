"""Per-user login and in-app activity for productivity tracking."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from ..extensions import db
from .base import UUIDPKMixin, TenantMixin


class UserActivityEvent(UUIDPKMixin, TenantMixin, db.Model):
    __tablename__ = "user_activity_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    summary: Mapped[str] = mapped_column(String(300), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )


class UserActivityDaily(UUIDPKMixin, TenantMixin, db.Model):
    """One Pacific-calendar-day rollup of active time and work counts."""

    __tablename__ = "user_activity_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "activity_date", name="uq_user_activity_daily_user_date"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    activity_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    active_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    page_views: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    api_writes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    logins: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    first_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
