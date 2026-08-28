"""Ship dates, PO shipments/receipts, line qty rollups, invoice 3-way match.

Reuses commitments as the material PO header (no parallel purchase_orders table).
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0062_po_shipments_receipts"
down_revision: Union[str, Sequence[str], None] = "0061_vendor_invoices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("commitments", sa.Column("promised_ship_date", sa.Date(), nullable=True))
    op.add_column("commitments", sa.Column("revised_ship_date", sa.Date(), nullable=True))
    op.add_column("commitments", sa.Column("actual_ship_date", sa.Date(), nullable=True))
    op.add_column("commitments", sa.Column("needed_on_site_date", sa.Date(), nullable=True))
    op.add_column(
        "commitments",
        sa.Column("fulfillment_status", sa.String(40), nullable=False, server_default="open"),
    )
    op.create_index("ix_commitments_fulfillment_status", "commitments", ["fulfillment_status"])

    op.add_column(
        "commitment_line_items",
        sa.Column("rfp_line_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "commitment_line_items",
        sa.Column("estimate_line_item_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "commitment_line_items",
        sa.Column("qty_shipped", sa.Numeric(15, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "commitment_line_items",
        sa.Column("qty_received", sa.Numeric(15, 4), nullable=False, server_default="0"),
    )
    op.add_column(
        "commitment_line_items",
        sa.Column("qty_invoiced", sa.Numeric(15, 4), nullable=False, server_default="0"),
    )
    op.create_foreign_key(
        "fk_commitment_line_items_rfp_line_item_id",
        "commitment_line_items",
        "rfp_line_items",
        ["rfp_line_item_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_commitment_line_items_estimate_line_item_id",
        "commitment_line_items",
        "estimate_line_items",
        ["estimate_line_item_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "purchase_order_shipments",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("commitment_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("carrier", sa.String(length=40), nullable=True),
        sa.Column("tracking_number", sa.String(length=120), nullable=True),
        sa.Column("tracking_url", sa.String(length=1024), nullable=True),
        sa.Column("shipment_status", sa.String(length=40), nullable=False, server_default="pending"),
        sa.Column("promised_ship_date", sa.Date(), nullable=True),
        sa.Column("actual_ship_date", sa.Date(), nullable=True),
        sa.Column("estimated_delivery_date", sa.Date(), nullable=True),
        sa.Column("actual_delivery_date", sa.Date(), nullable=True),
        sa.Column("last_note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_order_shipments_commitment_id", "purchase_order_shipments", ["commitment_id"])
    op.create_index("ix_purchase_order_shipments_shipment_status", "purchase_order_shipments", ["shipment_status"])

    op.create_table(
        "purchase_order_shipment_lines",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=False),
        sa.Column("commitment_line_item_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["shipment_id"], ["purchase_order_shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commitment_line_item_id"], ["commitment_line_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_purchase_order_shipment_lines_shipment_id", "purchase_order_shipment_lines", ["shipment_id"]
    )
    op.create_index(
        "ix_purchase_order_shipment_lines_line_id",
        "purchase_order_shipment_lines",
        ["commitment_line_item_id"],
    )

    op.create_table(
        "purchase_order_receipts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("commitment_id", sa.UUID(), nullable=False),
        sa.Column("shipment_id", sa.UUID(), nullable=True),
        sa.Column("received_on", sa.Date(), nullable=False),
        sa.Column("received_by_user_id", sa.UUID(), nullable=True),
        sa.Column("packing_slip_ref", sa.String(length=120), nullable=True),
        sa.Column("document_id", sa.UUID(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="posted"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shipment_id"], ["purchase_order_shipments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["received_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_order_receipts_commitment_id", "purchase_order_receipts", ["commitment_id"])
    op.create_index("ix_purchase_order_receipts_shipment_id", "purchase_order_receipts", ["shipment_id"])
    op.create_index("ix_purchase_order_receipts_status", "purchase_order_receipts", ["status"])

    op.create_table(
        "purchase_order_receipt_lines",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("receipt_id", sa.UUID(), nullable=False),
        sa.Column("commitment_line_item_id", sa.UUID(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["receipt_id"], ["purchase_order_receipts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commitment_line_item_id"], ["commitment_line_items.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_purchase_order_receipt_lines_receipt_id", "purchase_order_receipt_lines", ["receipt_id"])
    op.create_index(
        "ix_purchase_order_receipt_lines_line_id",
        "purchase_order_receipt_lines",
        ["commitment_line_item_id"],
    )

    op.add_column(
        "vendor_invoices",
        sa.Column("match_status", sa.String(32), nullable=False, server_default="unmatched"),
    )
    op.add_column("vendor_invoices", sa.Column("match_notes", sa.Text(), nullable=True))
    op.add_column(
        "vendor_invoices",
        sa.Column("match_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_vendor_invoices_match_status", "vendor_invoices", ["match_status"])


def downgrade() -> None:
    op.drop_index("ix_vendor_invoices_match_status", table_name="vendor_invoices")
    op.drop_column("vendor_invoices", "match_checked_at")
    op.drop_column("vendor_invoices", "match_notes")
    op.drop_column("vendor_invoices", "match_status")

    op.drop_index("ix_purchase_order_receipt_lines_line_id", table_name="purchase_order_receipt_lines")
    op.drop_index("ix_purchase_order_receipt_lines_receipt_id", table_name="purchase_order_receipt_lines")
    op.drop_table("purchase_order_receipt_lines")
    op.drop_index("ix_purchase_order_receipts_status", table_name="purchase_order_receipts")
    op.drop_index("ix_purchase_order_receipts_shipment_id", table_name="purchase_order_receipts")
    op.drop_index("ix_purchase_order_receipts_commitment_id", table_name="purchase_order_receipts")
    op.drop_table("purchase_order_receipts")
    op.drop_index("ix_purchase_order_shipment_lines_line_id", table_name="purchase_order_shipment_lines")
    op.drop_index("ix_purchase_order_shipment_lines_shipment_id", table_name="purchase_order_shipment_lines")
    op.drop_table("purchase_order_shipment_lines")
    op.drop_index("ix_purchase_order_shipments_shipment_status", table_name="purchase_order_shipments")
    op.drop_index("ix_purchase_order_shipments_commitment_id", table_name="purchase_order_shipments")
    op.drop_table("purchase_order_shipments")

    op.drop_constraint(
        "fk_commitment_line_items_estimate_line_item_id", "commitment_line_items", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_commitment_line_items_rfp_line_item_id", "commitment_line_items", type_="foreignkey"
    )
    op.drop_column("commitment_line_items", "qty_invoiced")
    op.drop_column("commitment_line_items", "qty_received")
    op.drop_column("commitment_line_items", "qty_shipped")
    op.drop_column("commitment_line_items", "estimate_line_item_id")
    op.drop_column("commitment_line_items", "rfp_line_item_id")

    op.drop_index("ix_commitments_fulfillment_status", table_name="commitments")
    op.drop_column("commitments", "fulfillment_status")
    op.drop_column("commitments", "needed_on_site_date")
    op.drop_column("commitments", "actual_ship_date")
    op.drop_column("commitments", "revised_ship_date")
    op.drop_column("commitments", "promised_ship_date")
