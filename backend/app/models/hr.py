"""HR module tables (Plan 19) — onboarding, policy acknowledgments, HR training assignments."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .document import Document
    from .wage_rate import WageRate


class HrOnboardingItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hr_onboarding_items"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class HrPolicyAcknowledgment(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hr_policy_acknowledgments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_version: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approval_request_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class HrTrainingAssignment(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "hr_training_assignments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_key: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])


class HrHireApplication(UUIDPKMixin, TimestampMixin, db.Model):
    """Hire wizard intake; I-9 / W-4 PII stored encrypted in ``*_json_encrypted`` columns."""

    __tablename__ = "hr_hire_applications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True
    )
    application_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    i9_section1_json_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    i9_section1_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    i9_signature_png: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    i9_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    i9_signed_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    w4_json_encrypted: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    w4_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    w4_signature_png: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    w4_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    w4_signed_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    hire_status: Mapped[str] = mapped_column(String(32), nullable=False, default="in_progress", index=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_for_review_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    hire_path: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, index=True)
    offer_position: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    offer_pay_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    offer_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    offer_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    offer_pending_role_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    reviewed_by: Mapped[Optional["User"]] = relationship(foreign_keys=[reviewed_by_user_id])
    offer_document: Mapped[Optional["Document"]] = relationship(foreign_keys=[offer_document_id])
    i9_document_files: Mapped[list["HrHireI9DocumentFile"]] = relationship(
        back_populates="hire_application",
        cascade="all, delete-orphan",
        order_by="HrHireI9DocumentFile.sort_order",
    )
    w4_document_files: Mapped[list["HrHireW4DocumentFile"]] = relationship(
        back_populates="hire_application",
        cascade="all, delete-orphan",
        order_by="HrHireW4DocumentFile.sort_order",
    )
    union_document_files: Mapped[list["HrHireUnionDocumentFile"]] = relationship(
        back_populates="hire_application",
        cascade="all, delete-orphan",
        order_by="HrHireUnionDocumentFile.sort_order",
    )


class HrHireI9DocumentFile(UUIDPKMixin, TimestampMixin, db.Model):
    """Photo of an I-9 List A / B / C supporting document for a hire wizard application."""

    __tablename__ = "hr_hire_i9_document_files"

    hire_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_hire_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_ext: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    hire_application: Mapped["HrHireApplication"] = relationship(back_populates="i9_document_files")


class HrHireW4DocumentFile(UUIDPKMixin, TimestampMixin, db.Model):
    """Photo of a signed W-4 or other W-4 supporting document for a hire wizard application."""

    __tablename__ = "hr_hire_w4_document_files"

    hire_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_hire_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    slot: Mapped[str] = mapped_column(String(16), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_ext: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    hire_application: Mapped["HrHireApplication"] = relationship(back_populates="w4_document_files")


class HrHireUnionDocumentFile(UUIDPKMixin, TimestampMixin, db.Model):
    """Photo of a union card or union dispatch slip for a hire wizard application."""

    __tablename__ = "hr_hire_union_document_files"

    hire_application_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hr_hire_applications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    original_filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_ext: Mapped[str] = mapped_column(String(16), nullable=False)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    hire_application: Mapped["HrHireApplication"] = relationship(back_populates="union_document_files")


class HrEmployeePayScale(UUIDPKMixin, TimestampMixin, db.Model):
    """Multiple pay schedules per employee (union scales, stipends, etc.). HR-owned; not prevailing wage reference rows."""

    __tablename__ = "hr_employee_pay_scales"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    pay_basis: Mapped[str] = mapped_column(String(32), nullable=False)
    hourly_rate: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    annual_salary: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    effective_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    effective_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    wage_rate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("wage_rates.id", ondelete="SET NULL"), nullable=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    wage_rate: Mapped[Optional["WageRate"]] = relationship(foreign_keys=[wage_rate_id])
    document: Mapped[Optional["Document"]] = relationship(foreign_keys=[document_id])


class HrEmployeeDocument(UUIDPKMixin, TimestampMixin, db.Model):
    """HR-held document links for an employee (offer letters, IDs, etc.); file lives in ``documents``."""

    __tablename__ = "hr_employee_documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )

    user: Mapped["User"] = relationship(foreign_keys=[user_id])
    document: Mapped[Optional["Document"]] = relationship(foreign_keys=[document_id])
