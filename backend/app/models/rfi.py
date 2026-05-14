"""Project-scoped RFIs (Procore-parity log / workflow fields).

Models in this module:

- ``Rfi``                  — the RFI header (one per Procore RFI #).
- ``RfiAssignee``          — users responsible for responding (per Procore).
- ``RfiDistribution``      — read-only distribution list members.
- ``RfiReply``             — discussion thread + Official Response (Phase 2).
- ``RfiAudit``             — change history (Phase 2).
- ``RfiRevision``          — immutable snapshot when revising a closed RFI
                              (Phase 5).
- ``RfiCustomFieldDef``    — per-company custom field registry (Phase 5).
- ``RfiCustomFieldValue``  — per-RFI custom field values (Phase 5).
- ``RfiConfigurableField`` — per-project fieldset (Phase 5).
- ``RfiSavedView``         — per-user / project / company saved views
                              (Phase 4).
- ``RfiColumnPref``        — per-user column display preferences (Phase 4).
- ``RfiNotificationLog``   — outbound email audit trail (Phase 3).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


# ---------------------------------------------------------------------------
# Enums (created in the migration)
# ---------------------------------------------------------------------------

rfi_status_enum = ENUM(
    "draft",
    "open",
    "closed",
    "closed_draft",
    name="rfi_status",
    create_type=False,
)

rfi_impact_choice_enum = ENUM(
    "yes",
    "yes_unknown",
    "no",
    "tbd",
    "na",
    name="rfi_impact_choice",
    create_type=False,
)

rfi_audit_action_enum = ENUM(
    "create",
    "edit",
    "status_change",
    "ball_in_court",
    "assignee_add",
    "assignee_remove",
    "distribution_add",
    "distribution_remove",
    "reply_add",
    "reply_delete",
    "official_response_set",
    "close",
    "reopen",
    "forward",
    "email_sent",
    "revision",
    "attachment_add",
    "attachment_remove",
    "restore",
    "delete",
    name="rfi_audit_action",
    create_type=False,
)

rfi_view_scope_enum = ENUM(
    "user",
    "project",
    "company",
    name="rfi_view_scope",
    create_type=False,
)

rfi_custom_field_type_enum = ENUM(
    "number",
    "date",
    "checkbox",
    "plain_text",
    name="rfi_custom_field_type",
    create_type=False,
)

rfi_field_requirement_enum = ENUM(
    "required",
    "optional",
    "hidden",
    name="rfi_field_requirement",
    create_type=False,
)


# ---------------------------------------------------------------------------
# RFI header
# ---------------------------------------------------------------------------


class Rfi(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfis"
    __table_args__ = (
        UniqueConstraint("project_id", "number", "revision_index", name="uq_rfis_project_number_rev"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    number: Mapped[int] = mapped_column(Integer, nullable=False)
    prefix: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    revision_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")

    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    question: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    general_information: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reference_text: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(rfi_status_enum, nullable=False, default="draft", index=True)
    is_private: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false", index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    date_initiated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    cost_impact_choice: Mapped[Optional[str]] = mapped_column(rfi_impact_choice_enum, nullable=True)
    cost_impact: Mapped[Optional[float]] = mapped_column(Numeric(15, 2), nullable=True)
    schedule_impact_choice: Mapped[Optional[str]] = mapped_column(rfi_impact_choice_enum, nullable=True)
    schedule_impact_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Free-text ball-in-court (display only; the true ball-in-court is the
    # assignee row with ``ball_in_court=True`` or the RFI Manager when no
    # assignee holds the ball).
    ball_in_court: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # Procore "Official Response": pointer to the chosen reply (set by the
    # RFI Manager). Plain text is kept too for backward compatibility with
    # the older bare-bones model.
    official_response_reply_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi_replies.id", ondelete="SET NULL", use_alter=True, name="fk_rfis_official_response_reply_id"),
        nullable=True,
    )
    official_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # People
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    rfi_manager_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    received_from_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    responsible_contractor_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Lookups (project-scoped)
    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_locations.id", ondelete="SET NULL"), nullable=True
    )
    spec_section_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_spec_sections.id", ondelete="SET NULL"), nullable=True
    )
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    project_stage_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_project_stages.id", ondelete="SET NULL"), nullable=True
    )
    sub_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_sub_jobs.id", ondelete="SET NULL"), nullable=True
    )

    # Drawings
    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True
    )
    drawing_number_text: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Phase 5 — revision pointers
    revision_of_rfi_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Free-form metadata bag (filters, sort tokens, etc.) — used by saved-view
    # filter chips so we don't have to migrate the schema for every UI tweak.
    extra: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    project = relationship("Project", back_populates="rfis")
    assignees: Mapped[List["RfiAssignee"]] = relationship(
        back_populates="rfi", cascade="all, delete-orphan", foreign_keys="RfiAssignee.rfi_id"
    )
    distribution: Mapped[List["RfiDistribution"]] = relationship(
        back_populates="rfi", cascade="all, delete-orphan", foreign_keys="RfiDistribution.rfi_id"
    )
    replies: Mapped[List["RfiReply"]] = relationship(
        back_populates="rfi",
        cascade="all, delete-orphan",
        foreign_keys="RfiReply.rfi_id",
        order_by="RfiReply.created_at.asc()",
    )
    audit_entries: Mapped[List["RfiAudit"]] = relationship(
        back_populates="rfi",
        cascade="all, delete-orphan",
        foreign_keys="RfiAudit.rfi_id",
        order_by="RfiAudit.created_at.desc()",
    )
    custom_values: Mapped[List["RfiCustomFieldValue"]] = relationship(
        back_populates="rfi", cascade="all, delete-orphan", foreign_keys="RfiCustomFieldValue.rfi_id"
    )


# ---------------------------------------------------------------------------
# Join tables: assignees + distribution
# ---------------------------------------------------------------------------


class RfiAssignee(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_assignees"
    __table_args__ = (UniqueConstraint("rfi_id", "user_id", name="uq_rfi_assignees_rfi_user"),)

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    ball_in_court: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    rfi: Mapped["Rfi"] = relationship(back_populates="assignees", foreign_keys=[rfi_id])
    user = relationship("User", foreign_keys=[user_id])


class RfiDistribution(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_distribution"
    __table_args__ = (UniqueConstraint("rfi_id", "user_id", name="uq_rfi_distribution_rfi_user"),)

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    rfi: Mapped["Rfi"] = relationship(back_populates="distribution", foreign_keys=[rfi_id])
    user = relationship("User", foreign_keys=[user_id])


# ---------------------------------------------------------------------------
# Replies + audit (Phase 2)
# ---------------------------------------------------------------------------


class RfiReply(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_replies"

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")

    rfi: Mapped["Rfi"] = relationship(back_populates="replies", foreign_keys=[rfi_id])
    author = relationship("User", foreign_keys=[author_user_id])


class RfiAudit(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_audit"

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(rfi_audit_action_enum, nullable=False, index=True)
    summary: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    before_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    after_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    rfi: Mapped["Rfi"] = relationship(back_populates="audit_entries", foreign_keys=[rfi_id])
    actor = relationship("User", foreign_keys=[actor_user_id])


# ---------------------------------------------------------------------------
# Revisions, custom fields, configurable fields (Phase 5)
# ---------------------------------------------------------------------------


class RfiRevision(UUIDPKMixin, TimestampMixin, db.Model):
    """Immutable snapshot of an RFI when ``revise`` is performed."""

    __tablename__ = "rfi_revisions"

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    revision_index: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)


class RfiCustomFieldDef(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_custom_field_defs"

    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(80), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    field_type: Mapped[str] = mapped_column(rfi_custom_field_type_enum, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RfiCustomFieldValue(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_custom_field_values"
    __table_args__ = (
        UniqueConstraint("rfi_id", "field_def_id", name="uq_rfi_custom_field_values_rfi_def"),
    )

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_def_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfi_custom_field_defs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    value_number: Mapped[Optional[float]] = mapped_column(Numeric(20, 6), nullable=True)
    value_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    value_bool: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    rfi: Mapped["Rfi"] = relationship(back_populates="custom_values", foreign_keys=[rfi_id])
    field_def = relationship("RfiCustomFieldDef", foreign_keys=[field_def_id])


class RfiConfigurableField(UUIDPKMixin, TimestampMixin, db.Model):
    """Per-project configurable fieldset: marks each Procore field
    required / optional / hidden (see Procore "Configurable Fieldsets")."""

    __tablename__ = "rfi_configurable_fields"
    __table_args__ = (
        UniqueConstraint("project_id", "field_key", name="uq_rfi_configurable_fields_project_field"),
    )

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    field_key: Mapped[str] = mapped_column(String(80), nullable=False)
    requirement: Mapped[str] = mapped_column(
        rfi_field_requirement_enum, nullable=False, default="optional"
    )


# ---------------------------------------------------------------------------
# Saved views + column prefs (Phase 4)
# ---------------------------------------------------------------------------


class RfiSavedView(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_saved_views"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    scope: Mapped[str] = mapped_column(rfi_view_scope_enum, nullable=False, default="user")
    owner_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    filters: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    sort: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    columns: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class RfiColumnPref(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_column_prefs"
    __table_args__ = (
        UniqueConstraint("user_id", "scope_key", name="uq_rfi_column_prefs_user_scope"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scope_key: Mapped[str] = mapped_column(String(120), nullable=False)
    columns: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    row_height: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)


# ---------------------------------------------------------------------------
# Notification log (Phase 3)
# ---------------------------------------------------------------------------


class RfiNotificationLog(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfi_notification_log"

    rfi_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfis.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    recipient_email: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    body_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
