"""Issued drawing packages belonging to a lead (bid set, IFC, revision)."""
from __future__ import annotations

import uuid
from datetime import date
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .estimate import Estimate
    from .lead_estimate import LeadEstimate


class DrawingSet(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "drawing_sets"

    lead_estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    lead_estimate: Mapped["LeadEstimate"] = relationship(
        "LeadEstimate",
        back_populates="drawing_sets",
    )
    estimates: Mapped[List["Estimate"]] = relationship(
        "Estimate",
        back_populates="drawing_set",
    )
