"""Amendable workflow engine: published definitions, live queues, frozen instances.

Definitions can change without a code deploy. Open instances keep the snapshot
copied at start; new subjects pick up the latest published definition.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class WorkflowDefinition(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_definitions"
    __table_args__ = (
        UniqueConstraint(
            "process_key",
            "version",
            "project_id",
            name="uq_workflow_definitions_key_version_project",
        ),
    )

    process_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    steps: Mapped[List["WorkflowDefinitionStep"]] = relationship(
        back_populates="definition",
        cascade="all, delete-orphan",
        order_by="WorkflowDefinitionStep.sort_order",
    )


class WorkflowDefinitionStep(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_definition_steps"

    definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queue_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    required_actions: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    on_approve_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    entry_condition: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    skippable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    automation: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    definition: Mapped["WorkflowDefinition"] = relationship(back_populates="steps")


class WorkflowQueue(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_queues"
    __table_args__ = (UniqueConstraint("process_key", "queue_key", name="uq_workflow_queues_process_key"),)

    process_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    queue_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)

    members: Mapped[List["WorkflowQueueMember"]] = relationship(
        back_populates="queue",
        cascade="all, delete-orphan",
    )


class WorkflowQueueMember(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_queue_members"
    __table_args__ = (UniqueConstraint("queue_id", "user_id", name="uq_workflow_queue_members_user"),)

    queue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_queues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    queue: Mapped["WorkflowQueue"] = relationship(back_populates="members")
    user = relationship("User", foreign_keys=[user_id])


class WorkflowInstance(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_instances"

    process_key: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    definition_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_definitions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    definition_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    snapshot: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="open", index=True)
    current_step_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)

    steps: Mapped[List["WorkflowInstanceStep"]] = relationship(
        back_populates="instance",
        cascade="all, delete-orphan",
        order_by="WorkflowInstanceStep.sort_order",
    )


class WorkflowInstanceStep(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "workflow_instance_steps"

    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    queue_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    required_actions: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    on_approve_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    entry_condition: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    skippable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    automation: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    assignee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    instance: Mapped["WorkflowInstance"] = relationship(back_populates="steps")
    assignee = relationship("User", foreign_keys=[assignee_user_id])
