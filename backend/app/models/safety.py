"""Project-scoped safety records (Plan 7 daily pretask)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

PRETASK_STATUSES = ("draft", "submitted")

PRETASK_CHECKLIST_KEYS = (
    "supervisor_walkthrough",
    "coordination_other_crafts",
    "equipment_check",
    "training_complete",
    "sufficient_personnel",
)

DEFAULT_COMPANY_NAME = "DOCON, INC"


def empty_pretask_checklist() -> dict[str, bool]:
    return {key: False for key in PRETASK_CHECKLIST_KEYS}


def empty_pretask_task() -> dict[str, Any]:
    return {"jha_complete": False, "task": "", "hazards": "", "steps": ""}


def empty_pretask_attendee() -> dict[str, str]:
    return {"print_name": "", "signature": ""}


def default_pretask_tasks() -> list[dict[str, Any]]:
    return [empty_pretask_task() for _ in range(4)]


def default_pretask_attendees() -> list[dict[str, str]]:
    return [empty_pretask_attendee() for _ in range(4)]


class DailyPretask(UUIDPKMixin, TimestampMixin, db.Model):
    """One daily pre-task safety plan per project, workday, and crew lead."""

    __tablename__ = "daily_pretasks"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "work_date",
            "crew_lead_user_id",
            name="uq_daily_pretasks_project_date_lead",
        ),
        UniqueConstraint("client_id", name="uq_daily_pretasks_client_id"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    crew_lead_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    daily_report_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("daily_reports.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    client_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False, default=DEFAULT_COMPANY_NAME)
    area_of_work: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    checklist: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    tasks: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    near_miss: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    near_miss_notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    required_permits: Mapped[str] = mapped_column(Text, nullable=False, default="")
    items_concerns: Mapped[str] = mapped_column(Text, nullable=False, default="")
    quality_previous_day: Mapped[str] = mapped_column(Text, nullable=False, default="")
    present_items_concerns: Mapped[str] = mapped_column(Text, nullable=False, default="")
    attendees: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    supervisor_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    supervisor_signature: Mapped[str] = mapped_column(Text, nullable=False, default="")
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    project = relationship("Project", foreign_keys=[project_id])
    crew_lead = relationship("User", foreign_keys=[crew_lead_user_id])
    created_by = relationship("User", foreign_keys=[created_by_user_id])
