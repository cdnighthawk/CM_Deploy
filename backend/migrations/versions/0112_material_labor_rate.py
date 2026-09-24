"""material_pricing: production rate (units per hour) for derived labor hours.

Revision ID: 0112_mat_labor
Revises: 0111_corr_thread
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0112_mat_labor"
down_revision: Union[str, Sequence[str], None] = "0111_corr_thread"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "material_pricing",
        sa.Column("labor_units_per_hour", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "material_pricing",
        sa.Column("labor_rate_unit", sa.String(length=10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("material_pricing", "labor_rate_unit")
    op.drop_column("material_pricing", "labor_units_per_hour")
