"""Field-app daily reports and jobsite photos."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
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
