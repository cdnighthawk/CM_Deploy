"""Field-app daily reports and jobsite photos."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

DAILY_REPORT_STATUSES = ("draft", "complete")

DEFAULT_DAILY_SECTIONS: dict[str, Any] = {
    "weather": {"conditions": "", "temp_f": None, "notes": ""},
    "manpower": [],
    "equipment": [],
    "deliveries": [],
    "work_performed": "",
    "delays": "",
    "photos": [],
    "notes": "",
}


class DailyReport(UUIDPKMixin, TimestampMixin, db.Model):
    """One daily report per project per calendar date."""

    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("project_id", "report_date", name="uq_daily_reports_project_date"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    report_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    sections: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project")
    photos = relationship("FieldPhoto", back_populates="daily_report")


class FieldPhoto(UUIDPKMixin, TimestampMixin, db.Model):
    """Jobsite photo captured from the field app."""

    __tablename__ = "field_photos"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    daily_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("daily_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    caption: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    location_text: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    taken_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    project = relationship("Project")
    daily_report = relationship("DailyReport", back_populates="photos")


TIME_ENTRY_STATUSES = ("open", "on_break", "closed")
TIME_PUNCH_KINDS = ("clock_in", "clock_out", "break_start", "break_end", "switch")
DEFAULT_GEOFENCE_RADIUS_M = 250


class TimeEntry(UUIDPKMixin, TimestampMixin, db.Model):
    """One open shift per user. A mid-day switch closes this row and opens another."""

    __tablename__ = "time_entries"
    __table_args__ = (
        UniqueConstraint("client_id", name="uq_time_entries_client_id"),
        Index(
            "uq_time_entries_one_open",
            "user_id",
            unique=True,
            postgresql_where=text("status <> 'closed'"),
        ),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"),
        nullable=True,
    )
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    clock_in_photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_photos.id", ondelete="SET NULL"),
        nullable=True,
    )
    clock_out_photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_photos.id", ondelete="SET NULL"),
        nullable=True,
    )

    punches = relationship("TimePunch", back_populates="entry", cascade="all, delete-orphan")


class TimePunch(UUIDPKMixin, TimestampMixin, db.Model):
    """Immutable clock event (in, out, break, switch)."""

    __tablename__ = "time_punches"
    __table_args__ = (UniqueConstraint("client_id", name="uq_time_punches_client_id"),)

    entry_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("time_entries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    lon: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    accuracy_m: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    geofence_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    geofence_distance_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    photo_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("field_photos.id", ondelete="SET NULL"),
        nullable=True,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    client_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    entry = relationship("TimeEntry", back_populates="punches")
