"""estimates: project labor-rate worksheet JSON.

Revision ID: 0120_est_labor
Revises: 0119_wr_wc_pct
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0120_est_labor"
down_revision: Union[str, Sequence[str], None] = "0119_wr_wc_pct"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("estimates")}
    if "labor_rates" not in cols:
        op.add_column("estimates", sa.Column("labor_rates", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("estimates")}
    if "labor_rates" in cols:
        op.drop_column("estimates", "labor_rates")
