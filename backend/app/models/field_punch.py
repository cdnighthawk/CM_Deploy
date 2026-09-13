"""FinishWorks Field punch list (Ours + GC slot). Separate from web ``punchlist_items``."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

PUNCH_LISTS = ("ours", "gc")
PUNCH_STATUSES = ("open", "in_progress", "ready_to_inspect", "closed")
PUNCH_TYPES = (
    "deficiency",
    "incomplete",
    "damage",
    "warranty",
    "safety",
    "held_for_others",
)
PUNCH_PRIORITIES = ("blocking", "normal", "cosmetic")
PUNCH_IMPACTS = ("none", "possible", "yes")
PUNCH_SOURCES = ("internal", "procore", "other")
PUNCH_TRADES = (
    "drywall",
    "framing",
    "paint",
    "ceilings",
    "flooring",
    "doors",
    "millwork",
    "insulation",
    "fireproofing",
    "other",
)
PUNCH_OPEN_STATUSES = ("open", "in_progress", "ready_to_inspect")


class FieldPunchItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "punch_items"
    __table_args__ = (
        UniqueConstraint("local_id", name="uq_punch_items_local_id"),
        Index("ix_punch_items_project_list_status", "project_id", "list", "status"),
        Index("ix_punch_items_project_updated", "project_id", "updated_at"),
    )

    local_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    list: Mapped[str] = mapped_column(String(12), nullable=False, default="ours")
    number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")
    type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="normal")
    location_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_locations.id", ondelete="SET NULL"), nullable=True
    )
    trade: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    assignee_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    due_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    schedule_impact: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    schedule_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    cost_impact: Mapped[str] = mapped_column(String(20), nullable=False, default="none")
    cost_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True
    )
    revision_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    pin_x: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    pin_y: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="internal")
    external_id: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    external_type: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    gc_manager: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    gc_approver: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notify_on_save: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status_changed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    distributions: Mapped[List["PunchDistribution"]] = relationship(
        back_populates="punch_item", cascade="all, delete-orphan"
    )
    notify_logs: Mapped[List["PunchNotifyLog"]] = relationship(
        back_populates="punch_item", cascade="all, delete-orphan"
    )


class PunchDistribution(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "punch_distributions"
    __table_args__ = (UniqueConstraint("local_id", name="uq_punch_distributions_local_id"),)

    local_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    punch_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("punch_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    punch_item: Mapped[FieldPunchItem] = relationship(back_populates="distributions")


class PunchNotifyLog(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "punch_notify_logs"

    punch_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("punch_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recipients_json: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="email")
    message_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    sent_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    punch_item: Mapped[FieldPunchItem] = relationship(back_populates="notify_logs")
