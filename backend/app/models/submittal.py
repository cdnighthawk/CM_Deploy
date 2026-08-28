"""Project-scoped submittals (Procore-style log + internal QC gate)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)
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
    "assignment",
    "ai_run",
    "checklist",
    "stamp",
    "revision",
    "hold_release",
    "ae_action",
    "completeness",
    "transmit",
    name="submittal_audit_action",
    create_type=False,
)

submittal_revision_documents = Table(
    "submittal_revision_documents",
    db.Model.metadata,
    Column(
        "revision_id",
        UUID(as_uuid=True),
        ForeignKey("submittal_revisions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "document_id",
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

submittal_estimate_line_items = Table(
    "submittal_estimate_line_items",
    db.Model.metadata,
    Column(
        "submittal_id",
        UUID(as_uuid=True),
        ForeignKey("submittals.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "estimate_line_item_id",
        UUID(as_uuid=True),
        ForeignKey("estimate_line_items.id", ondelete="CASCADE"),
        primary_key=True,
    ),
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

    submittal_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True, index=True)
    trade: Mapped[Optional[str]] = mapped_column(String(40), nullable=True, index=True)
    action_type: Mapped[str] = mapped_column(String(20), nullable=False, default="action")
    vendor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_reviewer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    workflow_instance_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_instances.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    current_revision_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittal_revisions.id", ondelete="SET NULL", use_alter=True, name="fk_submittals_current_revision"),
        nullable=True,
    )
    spec_requirements: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    linked_drawing_ids: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    rfp_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="SET NULL"), nullable=True
    )
    rfp_response_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    needed_by_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True, index=True)
    internally_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_to_ae_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ae_action: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    ae_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    public_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    public_token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="submittals")
    vendor = relationship("Company", foreign_keys=[vendor_id])
    assigned_reviewer = relationship("User", foreign_keys=[assigned_reviewer_id])
    workflow_instance = relationship("WorkflowInstance", foreign_keys=[workflow_instance_id])
    current_revision = relationship(
        "SubmittalRevision",
        foreign_keys=[current_revision_id],
        post_update=True,
    )
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
    revisions: Mapped[List["SubmittalRevision"]] = relationship(
        back_populates="submittal",
        cascade="all, delete-orphan",
        foreign_keys="SubmittalRevision.submittal_id",
        order_by="SubmittalRevision.created_at",
    )
    holds: Mapped[List["SubmittalHold"]] = relationship(
        back_populates="submittal",
        cascade="all, delete-orphan",
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


class SubmittalRevision(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "submittal_revisions"

    submittal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision: Mapped[str] = mapped_column(String(20), nullable=False, default="A")
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    package_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    completeness_score: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    ai_review_annotation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawing_annotations.id", ondelete="SET NULL"),
        nullable=True,
    )
    ai_status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_run")
    ai_overridden_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_findings: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    human_stamp: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    stamp_comments: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    checklist_complete: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rubber_stamp_suspect: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rush_exception: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rush_exception_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rush_exception_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    submittal: Mapped["Submittal"] = relationship(
        back_populates="revisions",
        foreign_keys=[submittal_id],
    )
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_user_id])
    documents: Mapped[List["Document"]] = relationship(
        "Document",
        secondary=submittal_revision_documents,
    )
    checklist_items: Mapped[List["SubmittalChecklistItem"]] = relationship(
        back_populates="revision",
        cascade="all, delete-orphan",
        order_by="SubmittalChecklistItem.sort_order",
    )


class SubmittalChecklistItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "submittal_checklist_items"

    revision_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittal_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    template_key: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    result: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="template")
    ai_finding_ref: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    disposition: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    completed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    revision: Mapped["SubmittalRevision"] = relationship(back_populates="checklist_items")


class SubmittalHold(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "submittal_holds"

    submittal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    hold_type: Mapped[str] = mapped_column(String(20), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    submittal: Mapped["Submittal"] = relationship(back_populates="holds")
