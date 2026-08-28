"""Procurement commitments — purchase orders and subcontracts (Sage CM–aligned).

`status` / `status_effective_date` / `approved_at` mirror Sage PO semantics:
committed cost and downstream analytics should key off ``approved`` plus an
effective status date. ``workflow_rule_active`` mirrors header lock while an
approval workflow is in flight. ``commitment_bill_allocations`` models one PO
linked to multiple vendor bills before a first-class invoices table exists.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .company import Company, Contact
    from .estimate import EstimateLineItem
    from .project import Project
    from .purchase_order import PurchaseOrderReceipt, PurchaseOrderShipment
    from .rfi_lookups import CostCode
    from .rfp import Rfp, RfpLineItem
    from .takeoff_line_item import TakeoffLineItem

commitment_kind_enum = ENUM(
    "purchase_order",
    "subcontract",
    name="commitment_kind",
    create_type=False,
)

commitment_status_enum = ENUM(
    "draft",
    "pending_submission",
    "pending",
    "not_approved",
    "approved",
    name="commitment_status",
    create_type=False,
)

commitment_resource_enum = ENUM(
    "material",
    "labor",
    "equipment",
    "subcontractor",
    "other",
    name="commitment_resource",
    create_type=False,
)


class Commitment(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "commitments"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    commitment_kind: Mapped[str] = mapped_column(commitment_kind_enum, nullable=False)
    reference_number: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(
        commitment_status_enum, nullable=False, default="draft", server_default="draft", index=True
    )
    status_effective_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    workflow_rule_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    retention_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD", server_default="USD")
    total_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(15, 2), nullable=True)
    rfp_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfps.id", ondelete="SET NULL"), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    textura_contract_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    issue_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    po_type: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    reminder_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    vendor_contact_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    vendor_address_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    issued_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    authorized_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    issued_by_address_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ship_to_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    default_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    default_cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True
    )
    default_tax_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    default_resource: Mapped[Optional[str]] = mapped_column(commitment_resource_enum, nullable=True)
    promised_ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    revised_ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    needed_on_site_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fulfillment_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="open", server_default="open", index=True
    )

    project: Mapped["Project"] = relationship("Project", back_populates="commitments")
    vendor: Mapped["Company"] = relationship("Company", foreign_keys=[vendor_company_id])
    vendor_contact: Mapped[Optional["Contact"]] = relationship("Contact", foreign_keys=[vendor_contact_id])
    issued_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[issued_by_user_id])
    authorized_by_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[authorized_by_user_id]
    )
    default_cost_code: Mapped[Optional["CostCode"]] = relationship(
        "CostCode", foreign_keys=[default_cost_code_id]
    )
    rfp: Mapped[Optional["Rfp"]] = relationship("Rfp", foreign_keys=[rfp_id])
    line_items: Mapped[List["CommitmentLineItem"]] = relationship(
        back_populates="commitment", cascade="all, delete-orphan", order_by="CommitmentLineItem.sort_order"
    )
    bill_allocations: Mapped[List["CommitmentBillAllocation"]] = relationship(
        back_populates="commitment", cascade="all, delete-orphan"
    )
    shipments: Mapped[List["PurchaseOrderShipment"]] = relationship(
        back_populates="commitment",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderShipment.sort_order",
    )
    receipts: Mapped[List["PurchaseOrderReceipt"]] = relationship(
        back_populates="commitment",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderReceipt.received_on",
    )

    @property
    def ship_date(self) -> date | None:
        """UI ship date: revised if set, otherwise promised."""
        return self.revised_ship_date or self.promised_ship_date

    @property
    def missed_ship_date(self) -> bool:
        effective = self.ship_date
        if effective is None or self.actual_ship_date is not None:
            return False
        return date.today() > effective

    @property
    def late_vs_job(self) -> bool:
        effective = self.ship_date
        if effective is None or self.needed_on_site_date is None:
            return False
        return effective > self.needed_on_site_date


class CommitmentLineItem(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "commitment_line_items"

    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cost_code_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="EA", server_default="EA")
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    line_total: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False, default=Decimal("0"))
    tax_code: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    item_number: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    resource: Mapped[Optional[str]] = mapped_column(commitment_resource_enum, nullable=True)
    delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    takeoff_line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("takeoff_line_items.id", ondelete="SET NULL"), nullable=True
    )
    rfp_line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("rfp_line_items.id", ondelete="SET NULL"), nullable=True
    )
    estimate_line_item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("estimate_line_items.id", ondelete="SET NULL"), nullable=True
    )
    qty_shipped: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    qty_invoiced: Mapped[Decimal] = mapped_column(
        Numeric(15, 4), nullable=False, default=Decimal("0"), server_default="0"
    )
    submittal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submittals.id", ondelete="SET NULL"), nullable=True, index=True
    )
    submittal_release_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )

    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="line_items")
    submittal = relationship("Submittal", foreign_keys=[submittal_id])
    cost_code: Mapped[Optional["CostCode"]] = relationship("CostCode", foreign_keys=[cost_code_id])
    takeoff_line_item: Mapped[Optional["TakeoffLineItem"]] = relationship(
        "TakeoffLineItem", foreign_keys=[takeoff_line_item_id]
    )
    rfp_line_item: Mapped[Optional["RfpLineItem"]] = relationship(
        "RfpLineItem", foreign_keys=[rfp_line_item_id]
    )
    estimate_line_item: Mapped[Optional["EstimateLineItem"]] = relationship(
        "EstimateLineItem", foreign_keys=[estimate_line_item_id]
    )


class CommitmentBillAllocation(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "commitment_bill_allocations"

    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vendor_bill_ref: Mapped[str] = mapped_column(String(120), nullable=False)
    allocated_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    billed_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="bill_allocations")
