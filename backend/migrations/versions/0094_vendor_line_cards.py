"""Vendor line cards, supply role, and CSI buy-from channels.

Revision ID: 0094_vendor_line
Revises: 0093_rfp_b2, 0093_est_spec
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0094_vendor_line"
down_revision: Union[str, Sequence[str], None] = ("0093_rfp_b2", "0093_est_spec")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("supply_role", sa.String(length=20), nullable=True))
    op.create_index("ix_companies_supply_role", "companies", ["supply_role"])

    op.create_table(
        "csi_buy_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("csi_spec_section", sa.String(length=6), nullable=False),
        sa.Column("buy_from", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("csi_spec_section", name="uq_csi_buy_channels_section"),
    )
    op.create_index("ix_csi_buy_channels_csi_spec_section", "csi_buy_channels", ["csi_spec_section"])

    op.create_table(
        "vendor_line_cards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("csi_spec_section", sa.String(length=6), nullable=False),
        sa.Column("manufacturer", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("company_id", "csi_spec_section", "manufacturer", name="uq_vendor_line_cards_company_csi_mfr"),
    )
    op.create_index("ix_vendor_line_cards_company_id", "vendor_line_cards", ["company_id"])
    op.create_index("ix_vendor_line_cards_csi_spec_section", "vendor_line_cards", ["csi_spec_section"])

    channels = sa.table(
        "csi_buy_channels",
        sa.column("csi_spec_section", sa.String),
        sa.column("buy_from", sa.String),
    )
    op.bulk_insert(
        channels,
        [
            {"csi_spec_section": "102600", "buy_from": "manufacturer"},
            {"csi_spec_section": "102800", "buy_from": "distributor"},
            {"csi_spec_section": "102100", "buy_from": "distributor"},
            {"csi_spec_section": "102113", "buy_from": "distributor"},
        ],
    )


def downgrade() -> None:
    op.drop_index("ix_vendor_line_cards_csi_spec_section", table_name="vendor_line_cards")
    op.drop_index("ix_vendor_line_cards_company_id", table_name="vendor_line_cards")
    op.drop_table("vendor_line_cards")
    op.drop_index("ix_csi_buy_channels_csi_spec_section", table_name="csi_buy_channels")
    op.drop_table("csi_buy_channels")
    op.drop_index("ix_companies_supply_role", table_name="companies")
    op.drop_column("companies", "supply_role")
