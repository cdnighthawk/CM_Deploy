"""Documents (polymorphic), Drawings (specialization), and DrawingAnnotations.

We use joined-table inheritance:
- ``documents`` holds every file in the platform (RFP responses, submittals,
  drawings, photos, AI reviews, etc.).
- ``drawings`` adds drawing-specific columns and shares the same PK.
"""
from __future__ import annotations

import uuid
from typing import List, Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text, event
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

document_type_enum = ENUM(
    "drawing",
    "rfi",
    "submittal",
    "specification",
    "contract",
    "change_order",
    "invoice",
    "photo",
    "report",
    "ai_review_export",
    "safety_doc",
    "permit",
    "other",
    name="document_type",
    create_type=True,
)

annotation_type_enum = ENUM(
    "measurement",
    "user_note",
    "ai_review",
    name="annotation_type",
    create_type=True,
)

annotation_severity_enum = ENUM(
    "info",
    "minor",
    "major",
    "critical",
    name="annotation_severity",
    create_type=True,
)


class Document(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "documents"

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    document_type: Mapped[str] = mapped_column(document_type_enum, nullable=False, index=True)
    title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    mime_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    file_size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    parent_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    uploaded_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    tags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    submittal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("submittals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    submittal = relationship("Submittal", back_populates="documents", foreign_keys=[submittal_id])
    submittal_pdf_annotation = relationship(
        "SubmittalPdfAnnotation",
        back_populates="document",
        uselist=False,
    )

    __mapper_args__ = {
        "polymorphic_on": document_type,
        "polymorphic_identity": "other",
    }


class Drawing(Document):
    """Specialization for architectural / engineering drawings."""

    __tablename__ = "drawings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sheet_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    sheet_title: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    discipline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    scale: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    calibration: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    drawing_set: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    revision: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # All revisions of the same physical sheet share one stable UUID (not necessarily a row id).
    drawing_series_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    annotations: Mapped[List["DrawingAnnotation"]] = relationship(
        back_populates="drawing", cascade="all, delete-orphan"
    )

    __mapper_args__ = {
        "polymorphic_identity": "drawing",
    }


@event.listens_for(Drawing, "before_insert")
def _drawing_default_series_id(mapper, connection, target: Drawing) -> None:
    """First revision of a sheet defaults to its own ``drawing_series_id``; upload code must reuse series for later revisions."""
    if target.drawing_series_id is None and target.id is not None:
        target.drawing_series_id = target.id


class DrawingAnnotation(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "drawing_annotations"

    drawing_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[str] = mapped_column(annotation_type_enum, nullable=False, index=True)
    data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    severity: Mapped[Optional[str]] = mapped_column(annotation_severity_enum, nullable=True)
    provider: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    issues: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cost_impact: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    delay_impact_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    drawing: Mapped["Drawing"] = relationship(back_populates="annotations")
