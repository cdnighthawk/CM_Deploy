"""Door schedule openings (Division 08) — schedule truth linked to takeoff lines."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin, TenantMixin

if TYPE_CHECKING:
    from .estimate import Estimate
    from .lead_estimate import LeadEstimate
    from .takeoff_line_item import TakeoffLineItem


class DoorOpening(UUIDPKMixin, TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "door_openings"
    __table_args__ = (
        UniqueConstraint("lead_estimate_id", "mark", name="uq_door_openings_lead_mark"),
        UniqueConstraint("estimate_id", "mark", name="uq_door_openings_estimate_mark"),
    )

    lead_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    lead_estimate: Mapped[Optional["LeadEstimate"]] = relationship("LeadEstimate", back_populates="door_openings")

    estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    estimate: Mapped[Optional["Estimate"]] = relationship("Estimate", foreign_keys=[estimate_id])

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

    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=Decimal("1"), server_default="1")
    leaf_count: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=Decimal("1"), server_default="1")
    width_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    height_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    thickness_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    hand: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    fire_rating_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    material: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    door_type_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    frame_type_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    frame_material: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    frame_construction: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    wall_thickness_in: Mapped[Optional[Decimal]] = mapped_column(Numeric(8, 2), nullable=True)
    frame_gauge: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    hardware_set_no: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    to_room: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    from_room: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    elevation: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    sheet_ref: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    scope_flag: Mapped[str] = mapped_column(String(20), nullable=False, default="in", server_default="in")
    source: Mapped[str] = mapped_column(String(40), nullable=False, default="manual", server_default="manual")
    conflicts: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    import_batch_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    source_row: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    takeoff_lines: Mapped[list["TakeoffLineItem"]] = relationship(
        "TakeoffLineItem",
        back_populates="door_opening",
        cascade="all, delete-orphan",
        order_by="TakeoffLineItem.sort_order",
    )
