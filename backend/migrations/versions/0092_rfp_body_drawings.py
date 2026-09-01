"""RFP body narrative, takeoff links, drawings join, lump-sum quotes.

Revision ID: 0092_rfp_body
Revises: 0090_rfp_quote
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0092_rfp_body"
down_revision: Union[str, Sequence[str], None] = "0090_rfp_quote"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rfps", sa.Column("line_source", sa.String(length=20), nullable=False, server_default="manual"))
    op.add_column("rfps", sa.Column("source_estimate_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("rfps", sa.Column("scope_of_work", sa.Text(), nullable=True))
    op.add_column("rfps", sa.Column("inclusions", sa.Text(), nullable=True))
    op.add_column("rfps", sa.Column("exclusions", sa.Text(), nullable=True))
    op.add_column("rfps", sa.Column("clarifications", sa.Text(), nullable=True))
    op.add_column("rfps", sa.Column("show_line_table", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("rfps", sa.Column("cc_estimator", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.create_index("ix_rfps_source_estimate_id", "rfps", ["source_estimate_id"])
    op.create_foreign_key(
        "fk_rfps_source_estimate_id",
        "rfps",
        "estimates",
        ["source_estimate_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.alter_column(
        "rfp_line_items",
        "quantity",
        existing_type=sa.Numeric(15, 4),
        nullable=True,
        existing_server_default="0",
    )
    op.add_column("rfp_line_items", sa.Column("csi_division", sa.String(length=120), nullable=True))
    op.add_column("rfp_line_items", sa.Column("trade", sa.String(length=120), nullable=True))
    op.add_column("rfp_line_items", sa.Column("room_area", sa.String(length=500), nullable=True))
    op.add_column("rfp_line_items", sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "rfp_line_items",
        sa.Column("source_takeoff_line_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "rfp_line_items",
        sa.Column("source_kind", sa.String(length=20), nullable=False, server_default="manual"),
    )
    op.add_column(
        "rfp_line_items",
        sa.Column("hidden_from_vendor", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "rfp_line_items",
        sa.Column("product_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index("ix_rfp_line_items_drawing_id", "rfp_line_items", ["drawing_id"])
    op.create_index("ix_rfp_line_items_source_takeoff_line_id", "rfp_line_items", ["source_takeoff_line_id"])
    op.create_foreign_key(
        "fk_rfp_line_items_drawing_id",
        "rfp_line_items",
        "drawings",
        ["drawing_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_rfp_line_items_source_takeoff_line_id",
        "rfp_line_items",
        "takeoff_line_items",
        ["source_takeoff_line_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("rfp_vendor_quotes", sa.Column("send_status", sa.String(length=20), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("lump_sum_amount", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfp_vendor_quotes", sa.Column("vendor_exclusions", sa.Text(), nullable=True))

    op.create_table(
        "rfp_drawings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rfp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("delivery", sa.String(length=20), nullable=False, server_default="link"),
        sa.Column("include_on_portal", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("frozen_pdf_path", sa.String(length=500), nullable=True),
        sa.Column("frozen_checksum", sa.String(length=64), nullable=True),
        sa.Column("frozen_bytes", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["rfp_id"], ["rfps.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rfp_drawings_rfp_id", "rfp_drawings", ["rfp_id"])
    op.create_index("ix_rfp_drawings_drawing_id", "rfp_drawings", ["drawing_id"])
    op.create_index("ix_rfp_drawings_document_id", "rfp_drawings", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_rfp_drawings_document_id", table_name="rfp_drawings")
    op.drop_index("ix_rfp_drawings_drawing_id", table_name="rfp_drawings")
    op.drop_index("ix_rfp_drawings_rfp_id", table_name="rfp_drawings")
    op.drop_table("rfp_drawings")

    op.drop_column("rfp_vendor_quotes", "vendor_exclusions")
    op.drop_column("rfp_vendor_quotes", "lump_sum_amount")
    op.drop_column("rfp_vendor_quotes", "send_status")

    op.drop_constraint("fk_rfp_line_items_source_takeoff_line_id", "rfp_line_items", type_="foreignkey")
    op.drop_constraint("fk_rfp_line_items_drawing_id", "rfp_line_items", type_="foreignkey")
    op.drop_index("ix_rfp_line_items_source_takeoff_line_id", table_name="rfp_line_items")
    op.drop_index("ix_rfp_line_items_drawing_id", table_name="rfp_line_items")
    op.drop_column("rfp_line_items", "product_snapshot")
    op.drop_column("rfp_line_items", "hidden_from_vendor")
    op.drop_column("rfp_line_items", "source_kind")
    op.drop_column("rfp_line_items", "source_takeoff_line_id")
    op.drop_column("rfp_line_items", "drawing_id")
    op.drop_column("rfp_line_items", "room_area")
    op.drop_column("rfp_line_items", "trade")
    op.drop_column("rfp_line_items", "csi_division")
    op.alter_column(
        "rfp_line_items",
        "quantity",
        existing_type=sa.Numeric(15, 4),
        nullable=False,
        existing_server_default="0",
    )

    op.drop_constraint("fk_rfps_source_estimate_id", "rfps", type_="foreignkey")
    op.drop_index("ix_rfps_source_estimate_id", table_name="rfps")
    op.drop_column("rfps", "cc_estimator")
    op.drop_column("rfps", "show_line_table")
    op.drop_column("rfps", "clarifications")
    op.drop_column("rfps", "exclusions")
    op.drop_column("rfps", "inclusions")
    op.drop_column("rfps", "scope_of_work")
    op.drop_column("rfps", "source_estimate_id")
    op.drop_column("rfps", "line_source")
