"""RFP core tables (Plan 5) — vendor quote requests with takeoff / narrative body."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

LINE_SOURCES = ("takeoff", "manual", "narrative")
SOURCE_KINDS = ("takeoff", "manual", "ai_suggest")
DRAWING_DELIVERIES = ("link", "attach", "both")


class Rfp(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfps"

    lead_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lead_estimates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="Draft", server_default="Draft")
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    public_token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    mail_tag: Mapped[Optional[str]] = mapped_column(String(16), nullable=True, unique=True, index=True)

    line_source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    source_estimate_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_spec_scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("estimate_spec_scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scope_of_work: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inclusions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exclusions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clarifications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    show_line_table: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    cc_estimator: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    last_send_batch: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    files_zip_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    files_zip_key: Mapped[Optional[str]] = mapped_column(String(700), nullable=True)
    files_zip_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    line_items: Mapped[List["RfpLineItem"]] = relationship(
        back_populates="rfp", cascade="all, delete-orphan", order_by="RfpLineItem.sort_order"
    )
    vendor_quotes: Mapped[List["RfpVendorQuote"]] = relationship(
        back_populates="rfp", cascade="all, delete-orphan"
    )
    drawings: Mapped[List["RfpDrawing"]] = relationship(
        back_populates="rfp", cascade="all, delete-orphan", order_by="RfpDrawing.sort_order"
    )


class RfpLineItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfp_line_items"

    rfp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 4), nullable=True)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="EA", server_default="EA")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    csi_division: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    trade: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    room_area: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("drawings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_takeoff_line_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("takeoff_line_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_kind: Mapped[str] = mapped_column(
        String(20), nullable=False, default="manual", server_default="manual"
    )
    hidden_from_vendor: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    product_snapshot: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)

    rfp = relationship("Rfp", back_populates="line_items")


class RfpVendorQuote(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfp_vendor_quotes"

    rfp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_label: Mapped[str] = mapped_column(String(255), nullable=False, default="Vendor", server_default="Vendor")
    vendor_company_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    vendor_contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    invited_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    invite_token: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, unique=True, index=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_from_mailbox: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    send_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="invited", server_default="invited")
    graph_inbound_message_id: Mapped[Optional[str]] = mapped_column(String(256), nullable=True, unique=True, index=True)
    from_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    from_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    mailbox: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    line_prices: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    lump_sum_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    vendor_exclusions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attachments: Mapped[Optional[Any]] = mapped_column(JSONB, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    rfp = relationship("Rfp", back_populates="vendor_quotes")


class RfpDrawing(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "rfp_drawings"

    rfp_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="CASCADE"), nullable=False, index=True
    )
    drawing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("drawings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    delivery: Mapped[str] = mapped_column(String(20), nullable=False, default="link", server_default="link")
    include_on_portal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    frozen_pdf_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    frozen_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    frozen_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    b2_bucket: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    b2_key: Mapped[Optional[str]] = mapped_column(String(700), nullable=True)
    sha256: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    byte_size: Mapped[Optional[int]] = mapped_column("bytes", Integer, nullable=True)
    content_type: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    original_filename: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    send_batch: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    rfp = relationship("Rfp", back_populates="drawings")
