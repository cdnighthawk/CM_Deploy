"""Door schedule openings (Division 08) — schedule truth linked to takeoff lines."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .lead_estimate import LeadEstimate
    from .takeoff_line_item import TakeoffLineItem


class DoorOpening(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "door_openings"
    __table_args__ = (
        UniqueConstraint("lead_estimate_id", "mark", name="uq_door_openings_lead_mark"),
    )

    lead_estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_estimate: Mapped["LeadEstimate"] = relationship("LeadEstimate", back_populates="door_openings")

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    mark: Mapped[str] = mapped_column(String(60), nullable=False, default="", server_default="")
    room: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    width: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    height: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    door_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    frame_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    hardware_set_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    fire_rating: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    handing: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    source_row: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    takeoff_lines: Mapped[list["TakeoffLineItem"]] = relationship(
        "TakeoffLineItem",
        back_populates="door_opening",
        cascade="all, delete-orphan",
        order_by="TakeoffLineItem.sort_order",
    )
