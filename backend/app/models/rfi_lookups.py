"""Project-scoped lookup tables used by the RFI tool (Procore parity).

These match Procore's RFI dropdowns:
- Locations (multi-tiered allowed via dotted ``path``)
- Spec Sections (CSI / spec book)
- Cost Codes
- Project Stages (RFI Prefix by Project Stage feature)
- Sub Jobs (WBS sub-jobs)

Each row is scoped to a project (``project_id``) so projects can have their own
sets. They are intentionally small/flat so they can be seeded from CSV or
configured per project.
"""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class Location(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_locations"
    __table_args__ = (UniqueConstraint("project_id", "path", name="uq_rfi_locations_project_path"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    path: Mapped[str] = mapped_column(String(500), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SpecSection(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_spec_sections"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_rfi_spec_sections_project_code"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Optional link to a hosted spec PDF (same-origin API path or absolute URL).
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)


class CostCode(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_cost_codes"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_rfi_cost_codes_project_code"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class ProjectStage(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_project_stages"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_rfi_project_stages_project_code"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    prefix: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SubJob(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_sub_jobs"
    __table_args__ = (UniqueConstraint("project_id", "code", name="uq_rfi_sub_jobs_project_code"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
