"""material_pricing: manufacturer catalog costs and labor factors.

Revision ID: 0003_material_pricing
Revises: 0002_wage_rates
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_material_pricing"
down_revision: Union[str, Sequence[str], None] = "0002_wage_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "material_pricing",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("manufacturer", sa.String(120), nullable=False),
        sa.Column("item", sa.String(120), nullable=False),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("mounting_type", sa.String(120), nullable=True),
        sa.Column("cost", sa.Numeric(12, 4), nullable=True),
        sa.Column("labor_per", sa.Numeric(10, 4), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("unit_of_measure", sa.String(20), nullable=False, server_default="EA"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("manufacturer", "item", name="uq_material_pricing_manufacturer_item"),
    )
    op.create_index("ix_material_pricing_manufacturer", "material_pricing", ["manufacturer"])
    op.create_index("ix_material_pricing_item", "material_pricing", ["item"])
    op.create_index("ix_material_pricing_category", "material_pricing", ["category"])


def downgrade() -> None:
    op.drop_table("material_pricing")
