"""Estimate first-pass: persist bid-by-location finding.

Revision ID: 0081_bid_loc
Revises: 0080_dwg_hyg
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0081_bid_loc"
down_revision: Union[str, Sequence[str], None] = "0080_dwg_hyg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("estimates", sa.Column("bid_location", postgresql.JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("estimates", "bid_location")
