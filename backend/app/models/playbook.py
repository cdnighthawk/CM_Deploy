"""Operational playbook checklist templates and runs (Plan 22)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .company import Company
    from .project import Project

checklist_run_status_enum = ENUM(
    "open",
    "complete",
    "cancelled",
    name="checklist_run_status",
    create_type=True,
)

checklist_run_step_status_enum = ENUM(
    "pending",
    "done",
    "skipped",
    name="checklist_run_step_status",
    create_type=True,
)


class ChecklistTemplate(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "checklist_templates"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    company: Mapped["Company"] = relationship()
    steps: Mapped[List["ChecklistTemplateStep"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ChecklistTemplateStep.sequence",
    )
    runs: Mapped[List["ChecklistRun"]] = relationship(back_populates="template")


class ChecklistTemplateStep(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "checklist_template_steps"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_templates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_assignee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    template: Mapped["ChecklistTemplate"] = relationship(back_populates="steps")
    default_assignee: Mapped[Optional["User"]] = relationship(
        foreign_keys=[default_assignee_user_id],
    )


class ChecklistRun(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "checklist_runs"

    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_templates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(checklist_run_status_enum, nullable=False, default="open")
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    template: Mapped["ChecklistTemplate"] = relationship(back_populates="runs")
    project: Mapped[Optional["Project"]] = relationship()
    created_by: Mapped[Optional["User"]] = relationship(foreign_keys=[created_by_user_id])
    run_steps: Mapped[List["ChecklistRunStep"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="ChecklistRunStep.sequence",
    )


class ChecklistRunStep(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "checklist_run_steps"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("checklist_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    assignee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(checklist_run_step_status_enum, nullable=False, default="pending")
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    run: Mapped["ChecklistRun"] = relationship(back_populates="run_steps")
    assignee: Mapped[Optional["User"]] = relationship(foreign_keys=[assignee_user_id])
    completed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[completed_by_user_id])
