"""Unified issues tracker (AI reviews, RFIs, punch, field, safety, website reports)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class Issue(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "tracker_issues"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_tracker_issues_source"),
    )

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="Minor", index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="New", index=True)
    trade: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cbc_citation: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    cost_impact: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    schedule_impact_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    sheet_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    linked_rfi_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    linked_change_order_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    events: Mapped[List["IssueEvent"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        order_by="IssueEvent.created_at.desc()",
    )


class IssueEvent(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "tracker_issue_events"

    issue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tracker_issues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    issue: Mapped[Issue] = relationship(back_populates="events")
