"""wage_rates: optional per-trade workers' comp percent.

Revision ID: 0119_wr_wc_pct
Revises: 0118_mat_mfr_url
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0119_wr_wc_pct"
down_revision: Union[str, Sequence[str], None] = "0118_mat_mfr_url"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("wage_rates")}
    if "workers_comp_pct" not in cols:
        op.add_column(
            "wage_rates",
            sa.Column("workers_comp_pct", sa.Numeric(8, 4), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("wage_rates")}
    if "workers_comp_pct" in cols:
        op.drop_column("wage_rates", "workers_comp_pct")
