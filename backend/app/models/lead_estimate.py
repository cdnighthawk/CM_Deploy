"""BuildingConnected (Autodesk) lead / estimate opportunities (CSV import).

Each row is one trade-scoped bid opportunity. BC column names appear in comments.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin


class LeadEstimate(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "lead_estimates"

    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Shared job UID. Many lead_estimates rows (one per trade) can point at one project.",
    )
    project = relationship("Project", foreign_keys=[project_id])

    external_id: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True, comment="CSV id"
    )
    external_parent_id: Mapped[Optional[str]] = mapped_column(
        String(64), nullable=True, index=True, comment="CSV parentId"
    )
    name: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    trade_name: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, index=True, comment="CSV tradeName"
    )
    submission_state: Mapped[Optional[str]] = mapped_column(
        String(60), nullable=True, index=True, comment="CSV submissionState"
    )
    outcome: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="CSV dueAt"
    )
    bc_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True, comment="CSV updatedAt"
    )
    bc_created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV createdAt"
    )
    is_archived: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment="CSV isArchived")
    final_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True, comment="CSV finalValue"
    )
    additional_info: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="CSV additionalInfo")
    architect: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    average_crew_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="CSV averageCrewSize")
    bid: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    client: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    client_values: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="CSV clientValues")
    competitors: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    contract_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="CSV contractDuration")
    contract_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV contractStartAt"
    )
    custom_tags: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="CSV customTags")
    decline_reasons: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="CSV declineReasons")
    default_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True, comment="CSV defaultCurrency")
    engineer: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    estimating_hours: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2), nullable=True, comment="CSV estimatingHours"
    )
    expected_finish_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV expectedFinishAt"
    )
    expected_start_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV expectedStartAt"
    )
    fee_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(7, 4), nullable=True, comment="CSV feePercentage"
    )
    follow_up_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV followUpAt"
    )
    group_children: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True, comment="CSV groupChildren")
    invited_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV invitedAt"
    )
    is_nda_required: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment="CSV isNdaRequired")
    is_parent: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment="CSV isParent")
    is_sealed_bidding: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment="CSV isSealedBidding")
    job_walk_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV jobWalkAt"
    )
    location: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    market_sector: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, comment="CSV marketSector")
    members: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    owning_office_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, comment="CSV owningOfficeId")
    priority: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    profit_margin: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(7, 4), nullable=True, comment="CSV profitMargin"
    )
    project_information: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="CSV projectInformation")
    project_is_public: Mapped[Optional[bool]] = mapped_column(
        Boolean, nullable=True, comment="CSV projectIsPublic"
    )
    project_size: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(15, 2), nullable=True, comment="CSV projectSize"
    )
    property_owner: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="CSV propertyOwner")
    property_tenant: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="CSV propertyTenant")
    request_type: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, comment="CSV requestType")
    rfis_due_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, comment="CSV rfisDueAt"
    )
    rom: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(60), nullable=True, index=True)
    trade_specific_instructions: Mapped[Optional[str]] = mapped_column(
        Text, nullable=True, comment="CSV tradeSpecificInstructions"
    )
    win_probability: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 4), nullable=True, comment="CSV winProbability"
    )
    workflow_bucket: Mapped[Optional[str]] = mapped_column(String(120), nullable=True, index=True)
    raw_row: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    crm_stage: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="New Lead",
        server_default="New Lead",
        index=True,
        comment="USIS CRM pipeline: New Lead, Invited, Estimating, Submitted, Awarded, Lost",
    )
    primary_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to estimates when Plan 4 table exists"
    )
    primary_rfp_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="FK to rfps when Plan 5 table exists"
    )

    takeoff_lines = relationship(
        "TakeoffLineItem",
        back_populates="lead_estimate",
        cascade="all, delete-orphan",
        order_by="TakeoffLineItem.sort_order",
    )
