"""Estimate spec-package scan: CSI sections, BOD/alternate mentions, vendor picks."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

SCAN_STATUSES = (
    "detecting",
    "review_sections",
    "extracting",
    "review_products",
    "vendors_ready",
    "rfp_drafted",
    "cancelled",
)
MENTION_ROLES = (
    "basis_of_design",
    "listed_alternate",
    "or_equal",
    "prohibited",
    "schedule_item",
)
MATCH_STATUSES = ("unmatched", "family_matched", "sku_matched", "needs_configurator")
VENDOR_REASONS = ("bod_house", "listed_alternate", "past_award", "trade_tag", "manual")


class SpecTradeMap(UUIDPKMixin, TimestampMixin, db.Model):
    """Office allow-list of CSI prefixes USIS actually bids."""

    __tablename__ = "spec_trade_map"
    __table_args__ = (UniqueConstraint("csi_prefix", name="uq_spec_trade_map_csi_prefix"),)

    csi_prefix: Mapped[str] = mapped_column(String(20), nullable=False)
    trade_label: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    default_in_scope: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class EstimateSpecScan(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_spec_scans"

    estimate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="detecting", server_default="detecting")
    provider: Mapped[str] = mapped_column(String(40), nullable=False, default="llama4-scout", server_default="llama4-scout")
    model_version: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    error_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    progress_text: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    sections: Mapped[List["EstimateSpecSection"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        order_by="EstimateSpecSection.csi_code",
    )
    vendors: Mapped[List["EstimateSpecVendor"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )


class EstimateSpecSection(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_spec_sections"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimate_spec_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    csi_code: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")
    in_scope: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    out_of_trade: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    shop_alternates: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    page_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    page_label: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    estimator_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    scan: Mapped["EstimateSpecScan"] = relationship(back_populates="sections")
    mentions: Mapped[List["EstimateSpecMention"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
    )


class EstimateSpecMention(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_spec_mentions"

    section_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimate_spec_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    mention_role: Mapped[str] = mapped_column(String(40), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    product_line: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    model_no: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    finish_note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    or_equal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    substitution_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_cite: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    material_pricing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("material_pricing.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    configurator_key: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    match_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="unmatched", server_default="unmatched"
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    product_snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    section: Mapped["EstimateSpecSection"] = relationship(back_populates="mentions")


class EstimateSpecVendor(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "estimate_spec_vendors"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimate_spec_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    suggested_reason: Mapped[str] = mapped_column(String(40), nullable=False, default="manual", server_default="manual")
    selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    rfp_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rfps.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sections: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    scan: Mapped["EstimateSpecScan"] = relationship(back_populates="vendors")
