"""Master schedule of values for the owner prime contract (project-scoped)."""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .project import Project


class PrimeContractSovLine(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "prime_contract_sov_lines"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("prime_contract_sov_lines.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    phase_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    scheduled_value: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))

    project: Mapped["Project"] = relationship("Project", back_populates="prime_contract_sov_lines")
