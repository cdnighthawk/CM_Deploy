"""Project-scoped submittals (Procore-style log / workflow fields)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

submittal_audit_action_enum = ENUM(
    "create",
    "edit",
    "status_change",
    "ball_in_court",
    "attachment_add",
    "attachment_remove",
    "annotation_save",
    "delete",
    name="submittal_audit_action",
    create_type=False,
)


class Submittal(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "submittals"
    __table_args__ = (UniqueConstraint("project_id", "number", name="uq_submittals_project_number"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    spec_section: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    submittal_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="draft", index=True)

    ball_in_court: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    responsible_contractor: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    submit_by_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    received_from: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    returned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    approvers: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    project = relationship("Project", back_populates="submittals")
    audit_entries: Mapped[List["SubmittalAudit"]] = relationship(
        back_populates="submittal",
        cascade="all, delete-orphan",
    )
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        back_populates="submittal",
        foreign_keys="Document.submittal_id",
    )
    line_items: Mapped[List["SubmittalLineItem"]] = relationship(
        back_populates="submittal",
        cascade="all, delete-orphan",
        order_by="SubmittalLineItem.sort_order",
    )


class SubmittalLineItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "submittal_line_items"

    submittal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    spec_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi_spec_sections.id", ondelete="SET NULL"),
        nullable=True,
    )
    spec_section_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    manufacturer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    catalog_product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("manufacturer_product_data.id", ondelete="SET NULL"),
        nullable=True,
    )
    pdf_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    submittal: Mapped["Submittal"] = relationship(back_populates="line_items", foreign_keys=[submittal_id])


class SubmittalAudit(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "submittal_audit"

    submittal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(submittal_audit_action_enum, nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    submittal: Mapped["Submittal"] = relationship(back_populates="audit_entries", foreign_keys=[submittal_id])
    actor = relationship("User", foreign_keys=[actor_user_id])


class SubmittalPdfAnnotation(UUIDPKMixin, TimestampMixin, db.Model):
    """One persisted markup layer per attachment (``document_id``)."""

    __tablename__ = "submittal_pdf_annotations"
    __table_args__ = (UniqueConstraint("document_id", name="uq_submittal_pdf_annotations_document"),)

    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload_json: Mapped[Any] = mapped_column(JSONB, nullable=False, default=list)

    document = relationship("Document", back_populates="submittal_pdf_annotation")
    author = relationship("User", foreign_keys=[author_user_id])
