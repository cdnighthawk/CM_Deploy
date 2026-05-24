"""Procurement lookups — project directory and PO types."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import UUIDPKMixin

if TYPE_CHECKING:
    from .company import Company
    from .project import Project

commitment_resource_enum = db.Enum(
    "material",
    "labor",
    "equipment",
    "subcontractor",
    "other",
    name="commitment_resource",
    create_type=False,
)

COMMITMENT_RESOURCES = frozenset(
    {"material", "labor", "equipment", "subcontractor", "other"}
)


class ProcurementPoType(UUIDPKMixin, db.Model):
    __tablename__ = "procurement_po_types"

    code: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class ProjectDirectoryCompany(UUIDPKMixin, db.Model):
    __tablename__ = "project_directory_companies"
    __table_args__ = (UniqueConstraint("project_id", "company_id", name="uq_project_directory_company"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    project: Mapped["Project"] = relationship("Project", foreign_keys=[project_id])
    company: Mapped["Company"] = relationship("Company", foreign_keys=[company_id])
