"""Office timekeeping tables. Field TimeEntry/TimePunch stay in field_ops."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

TIME_FLAG_TYPES = (
    "offsite",
    "blocked_override",
    "gps_denied",
    "open_punch",
    "overlap",
    "missing_meal",
    "missing_rest",
    "missing_signoff",
    "edited_after_sign",
    "cost_code_missing",
    "wrong_project",
    "clock_skew",
    "injury_reported",
)
TIME_FLAG_STATUSES = ("open", "accepted", "corrected", "dismissed")
TIMECARD_PERIOD_STATUSES = ("open", "reviewing", "locked", "exported")
GEOFENCE_MODES = ("flag", "block")
GEOFENCE_SHAPES = ("circle", "polygon")


class TimeCostCode(UUIDPKMixin, TimestampMixin, db.Model):
    """Company labor-bucket library for punches. Not Sage/JCC SKUs."""

    __tablename__ = "time_cost_codes"
    __table_args__ = (UniqueConstraint("code", name="uq_time_cost_codes_code"),)

    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    trade: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_billable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True
    )


class ProjectTimeCostCode(db.Model):
    __tablename__ = "project_time_cost_codes"
    __table_args__ = (UniqueConstraint("project_id", "time_cost_code_id", name="uq_project_time_cost_codes"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    time_cost_code_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_cost_codes.id", ondelete="CASCADE"), primary_key=True
    )
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    favorite: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class EmployeeTimeProfile(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "employee_time_profiles"
    __table_args__ = (UniqueConstraint("user_id", name="uq_employee_time_profiles_user"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    classification: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    union_local: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    prevailing_class: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    default_cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    ot_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    dt_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    burden_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_clock_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProjectGeofence(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "project_geofences"
    __table_args__ = (UniqueConstraint("project_id", name="uq_project_geofences_project"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="flag")
    shape: Mapped[str] = mapped_column(String(20), nullable=False, default="circle")
    center_lat: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    center_lon: Mapped[Optional[float]] = mapped_column(Numeric(10, 7), nullable=True)
    radius_m: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    polygon_geojson: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    reminder_mode: Mapped[str] = mapped_column(String(40), nullable=False, default="off")
    timezone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    shift_end_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class TimeBreadcrumb(UUIDPKMixin, db.Model):
    __tablename__ = "time_breadcrumbs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    time_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    lat: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    lon: Mapped[float] = mapped_column(Numeric(10, 7), nullable=False)
    acc: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TimeFlag(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "time_flags"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    time_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("time_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    work_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    flag_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TimecardDay(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "timecard_days"
    __table_args__ = (UniqueConstraint("user_id", "work_date", name="uq_timecard_days_user_date"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    ot_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    dt_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    premium_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    meal_minutes: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    signature_png_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    employee_attested_accurate: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    injury_reported: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    injury_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TimecardPeriod(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "timecard_periods"

    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    exported_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exported_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    export_file_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    workflow_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True
    )
    policy_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class TimecardPeriodEmployee(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "timecard_period_employees"
    __table_args__ = (UniqueConstraint("period_id", "user_id", name="uq_timecard_period_employees"),)

    period_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("timecard_periods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    regular_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    ot_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    dt_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    premium_hours: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False, default=Decimal("0"))
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    signature_png_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    workflow_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)

    period = relationship("TimecardPeriod")
