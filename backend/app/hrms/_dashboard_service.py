"""Aggregates for HRMS dashboards."""
from __future__ import annotations

from typing import Any

from sqlalchemy import func, select

from ..extensions import db
from ..models.auth import User
from ..models.hrms_core import (
    HrmsEmployeeProfile,
    HrmsExpenseReport,
    HrmsGoal,
    HrmsLeaveRequest,
    HrmsModuleSetting,
    HrmsShift,
    HrmsTimesheetPeriod,
)


def _feature_flags() -> dict[str, Any]:
    row = db.session.scalar(select(HrmsModuleSetting).where(HrmsModuleSetting.key == "feature_flags"))
    if row is None or not isinstance(row.value, dict):
        return {}
    return dict(row.value)


def build_dashboard_payload(*, scope: str) -> dict[str, Any]:
    """``scope`` is ``admin`` | ``manager`` | ``employee`` (UI hint only for now)."""
    flags = _feature_flags()
    n_profiles = db.session.scalar(select(func.count()).select_from(HrmsEmployeeProfile)) or 0
    n_users = db.session.scalar(select(func.count()).select_from(User).where(User.is_active.is_(True))) or 0
    n_pending_leave = db.session.scalar(
        select(func.count()).select_from(HrmsLeaveRequest).where(HrmsLeaveRequest.status == "pending")
    ) or 0
    n_draft_timesheets = db.session.scalar(
        select(func.count()).select_from(HrmsTimesheetPeriod).where(HrmsTimesheetPeriod.status == "draft")
    ) or 0
    n_shifts_upcoming = db.session.scalar(select(func.count()).select_from(HrmsShift)) or 0
    n_active_goals = db.session.scalar(select(func.count()).select_from(HrmsGoal).where(HrmsGoal.status == "active")) or 0
    n_expense_open = db.session.scalar(
        select(func.count())
        .select_from(HrmsExpenseReport)
        .where(HrmsExpenseReport.status.in_(("draft", "submitted")))
    ) or 0

    return {
        "scope": scope,
        "feature_flags": flags,
        "counts": {
            "employee_profiles": int(n_profiles),
            "active_directory_users": int(n_users),
            "leave_requests_pending": int(n_pending_leave),
            "timesheet_periods_draft": int(n_draft_timesheets),
            "shifts_total": int(n_shifts_upcoming),
            "goals_active": int(n_active_goals),
            "expense_reports_open": int(n_expense_open),
        },
        "notes": [
            "Counts are global placeholders until manager team scoping and per-employee filters are wired.",
            "Recruitment remains disabled via feature_flags.recruitment = false.",
        ],
    }
