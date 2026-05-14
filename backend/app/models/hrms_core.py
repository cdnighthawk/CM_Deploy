"""HRMS tables (Plan HRMS) — org, profiles, leave, time, shifts, goals, reviews, expenses, GDPR, audit."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

class HrmsOrgUnit(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_org_units"

    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hrms_org_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HrmsModuleSetting(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_module_settings"

    key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class HrmsLeaveType(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_leave_types"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    requires_attachment: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accrual_hours_per_month: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_carryover_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class HrmsEmployeeProfile(TimestampMixin, db.Model):
    """1:1 extension of ``users`` for HR org + employment fields."""

    __tablename__ = "hrms_employee_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    org_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hrms_org_units.id", ondelete="SET NULL"), nullable=True, index=True
    )
    manager_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    termination_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    employment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    custom_fields: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    pii_storage_hint: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class HrmsLeaveBalance(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_leave_balances"
    __table_args__ = (UniqueConstraint("user_id", "leave_type_id", "accrual_year", name="uq_hrms_leave_balance_user_type_year"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_leave_types.id", ondelete="CASCADE"), nullable=False)
    accrual_year: Mapped[int] = mapped_column(Integer, nullable=False)
    balance_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))
    accrued_ytd_hours: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("0"))


class HrmsLeaveRequest(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_leave_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_leave_types.id", ondelete="RESTRICT"), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    hours_requested: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class HrmsTimesheetPeriod(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_timesheet_periods"
    __table_args__ = (UniqueConstraint("user_id", "period_start", name="uq_hrms_timesheet_period_user_start"),)

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class HrmsTimesheetEntry(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_timesheet_entries"

    period_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_timesheet_periods.id", ondelete="CASCADE"), nullable=False, index=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    hours_worked: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    filled_from_leave: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)


class HrmsShift(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_shifts"

    org_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_org_units.id", ondelete="SET NULL"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class HrmsShiftAssignment(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_shift_assignments"
    __table_args__ = (UniqueConstraint("shift_id", "user_id", name="uq_hrms_shift_assignment_shift_user"),)

    shift_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_shifts.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    assignment_status: Mapped[str] = mapped_column(String(32), nullable=False, default="assigned")


class HrmsShiftSwap(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_shift_swaps"

    from_assignment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hrms_shift_assignments.id", ondelete="CASCADE"), nullable=False
    )
    to_shift_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_shifts.id", ondelete="SET NULL"), nullable=True)
    target_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class HrmsGoal(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_goals"

    owner_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    scope: Mapped[str] = mapped_column(String(16), nullable=False, default="individual")
    team_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    target_metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class HrmsGoalUpdate(UUIDPKMixin, db.Model):
    __tablename__ = "hrms_goal_updates"

    goal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_goals.id", ondelete="CASCADE"), nullable=False, index=True)
    author_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    progress_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HrmsReviewCycle(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_review_cycles"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    opens_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    closes_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    template_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class HrmsReviewInstance(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_review_instances"

    cycle_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_review_cycles.id", ondelete="CASCADE"), nullable=False)
    subject_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    meta: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class HrmsReviewScore(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_review_scores"

    instance_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_review_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    reviewer_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    scores: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class HrmsExpenseReport(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_expense_reports"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    approver_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class HrmsExpenseLine(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hrms_expense_lines"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("hrms_expense_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    spent_at: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    category: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    receipt_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)


class HrmsNotification(UUIDPKMixin, db.Model):
    __tablename__ = "hrms_notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HrmsGdprConsent(UUIDPKMixin, db.Model):
    __tablename__ = "hrms_gdpr_consents"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(120), nullable=False)
    consent_version: Mapped[str] = mapped_column(String(40), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    withdrawn_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class HrmsAuditLog(UUIDPKMixin, db.Model):
    __tablename__ = "hrms_audit_logs"

    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
