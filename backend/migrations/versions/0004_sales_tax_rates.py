"""Create sales_tax_rates (CDTFA reference rates).

Revision ID: 0004_sales_tax_rates
Revises: 0003_material_pricing
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_sales_tax_rates"
down_revision: Union[str, Sequence[str], None] = "0003_material_pricing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sales_tax_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(2), nullable=False, server_default="CA"),
        sa.Column("location", sa.String(255), nullable=False),
        sa.Column("rate", sa.Numeric(8, 6), nullable=False),
        sa.Column("county", sa.String(120), nullable=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="CDTFA"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "state",
            "location",
            "type",
            name="uq_sales_tax_rates_state_location_type",
        ),
    )
    op.create_index("ix_sales_tax_rates_state", "sales_tax_rates", ["state"])
    op.create_index("ix_sales_tax_rates_location", "sales_tax_rates", ["location"])
    op.create_index("ix_sales_tax_rates_county", "sales_tax_rates", ["county"])


def downgrade() -> None:
    op.drop_table("sales_tax_rates")
