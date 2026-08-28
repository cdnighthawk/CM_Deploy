"""Material PO shipments and receipts attached to purchase-order commitments.

The PO header and lines remain ``Commitment`` / ``CommitmentLineItem``.
These tables track carrier shipments (multiple per PO) and on-site receipts
for 3-way match. Vendor bills reuse ``VendorInvoice`` in Financials/AP.
"""
from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Date, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from .base import TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from .auth import User
    from .commitment import Commitment, CommitmentLineItem
    from .document import Document


SHIPMENT_STATUSES = frozenset(
    {"pending", "in_transit", "out_for_delivery", "delivered", "exception", "cancelled"}
)
RECEIPT_STATUSES = frozenset({"draft", "posted", "void"})
FULFILLMENT_STATUSES = frozenset(
    {"open", "partially_shipped", "shipped", "partially_received", "received", "closed"}
)
INVOICE_MATCH_STATUSES = frozenset({"unmatched", "quantity_ok", "amount_ok", "matched", "exception"})


class PurchaseOrderShipment(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "purchase_order_shipments"

    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    carrier: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    tracking_number: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    tracking_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    shipment_status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="pending", server_default="pending", index=True
    )
    promised_ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_ship_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    estimated_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_delivery_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="shipments")
    created_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by_user_id])
    lines: Mapped[List["PurchaseOrderShipmentLine"]] = relationship(
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderShipmentLine.sort_order",
    )


class PurchaseOrderShipmentLine(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "purchase_order_shipment_lines"

    shipment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commitment_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commitment_line_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    shipment: Mapped["PurchaseOrderShipment"] = relationship("PurchaseOrderShipment", back_populates="lines")
    commitment_line_item: Mapped["CommitmentLineItem"] = relationship(
        "CommitmentLineItem", foreign_keys=[commitment_line_item_id]
    )


class PurchaseOrderReceipt(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "purchase_order_receipts"

    commitment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    shipment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_shipments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    received_on: Mapped[date] = mapped_column(Date, nullable=False)
    received_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    packing_slip_ref: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="posted", server_default="posted", index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    commitment: Mapped["Commitment"] = relationship("Commitment", back_populates="receipts")
    shipment: Mapped[Optional["PurchaseOrderShipment"]] = relationship(
        "PurchaseOrderShipment", foreign_keys=[shipment_id]
    )
    received_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[received_by_user_id])
    document: Mapped[Optional["Document"]] = relationship("Document", foreign_keys=[document_id])
    lines: Mapped[List["PurchaseOrderReceiptLine"]] = relationship(
        back_populates="receipt",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderReceiptLine.sort_order",
    )


class PurchaseOrderReceiptLine(UUIDPKMixin, TimestampMixin, db.Model):
    __tablename__ = "purchase_order_receipt_lines"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("purchase_order_receipts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    commitment_line_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("commitment_line_items.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False, default=Decimal("0"))
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    receipt: Mapped["PurchaseOrderReceipt"] = relationship("PurchaseOrderReceipt", back_populates="lines")
    commitment_line_item: Mapped["CommitmentLineItem"] = relationship(
        "CommitmentLineItem", foreign_keys=[commitment_line_item_id]
    )
