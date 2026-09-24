"""Job-level door / frame type catalog (elevations D4 / F2)."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin, TenantMixin

if False:  # TYPE_CHECKING without circular import at runtime
    from .estimate import Estimate


class OpeningType(UUIDPKMixin, TimestampMixin, TenantMixin, db.Model):
    __tablename__ = "opening_types"
    __table_args__ = (
        UniqueConstraint("estimate_id", "kind", "code", name="uq_opening_types_estimate_kind_code"),
    )

    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    estimate: Mapped["Estimate"] = relationship("Estimate", foreign_keys=[estimate_id])

    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="door", server_default="door")
    code: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
