"""Union dispatch paperwork per employee and project (revision chain on pay changes)."""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .document import Document
    from .hr import HrEmployeePayScale, HrHireUnionDocumentFile
    from .project import Project


class HrEmployeeDispatch(UUIDPKMixin, TimestampMixin, db.Model):
    """One dispatch record per employee per project revision (new revision when pay changes)."""

    __tablename__ = "hr_employee_dispatches"
    __table_args__ = (
        UniqueConstraint("user_id", "project_id", "revision", name="uq_hr_dispatch_user_project_rev"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_employee_dispatches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    pay_scale_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_employee_pay_scales.id", ondelete="SET NULL"),
        nullable=True,
    )
    hourly_rate_snapshot: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    union_document_file_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_hire_union_document_files.id", ondelete="SET NULL"),
        nullable=True,
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    project: Mapped["Project"] = relationship(foreign_keys=[project_id])
    supersedes: Mapped[Optional["HrEmployeeDispatch"]] = relationship(
        remote_side="HrEmployeeDispatch.id", foreign_keys=[supersedes_id]
    )
    pay_scale: Mapped[Optional["HrEmployeePayScale"]] = relationship(foreign_keys=[pay_scale_id])
    union_document_file: Mapped[Optional["HrHireUnionDocumentFile"]] = relationship(
        foreign_keys=[union_document_file_id]
    )
    document: Mapped[Optional["Document"]] = relationship(foreign_keys=[document_id])
