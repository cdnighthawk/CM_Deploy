"""material_pricing: numeric sheet width/height in inches.

Revision ID: 0109_mat_size
Revises: 0108_act_daily
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0109_mat_size"
down_revision: Union[str, Sequence[str], None] = "0108_act_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "material_pricing",
        sa.Column("size_width_in", sa.Numeric(10, 4), nullable=True),
    )
    op.add_column(
        "material_pricing",
        sa.Column("size_height_in", sa.Numeric(10, 4), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("material_pricing", "size_height_in")
    op.drop_column("material_pricing", "size_width_in")
