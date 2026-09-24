"""material_pricing: numeric depth in inches (lockers, cabinets).

Revision ID: 0117_mat_depth
Revises: 0116_saas_admin_v2
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0117_mat_depth"
down_revision: Union[str, Sequence[str], None] = "0116_saas_admin_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("material_pricing")}
    if "size_depth_in" not in cols:
        op.add_column(
            "material_pricing",
            sa.Column("size_depth_in", sa.Numeric(10, 4), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("material_pricing", "size_depth_in")
