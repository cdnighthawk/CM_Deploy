"""takeoff lines: trade rate + mixed-trade crew on labor tasks.

Revision ID: 0121_line_trade
Revises: 0120_est_labor
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0121_line_trade"
down_revision: Union[str, Sequence[str], None] = "0120_est_labor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("takeoff_line_items")}
    if "wage_rate_id" not in cols:
        op.add_column(
            "takeoff_line_items",
            sa.Column("wage_rate_id", postgresql.UUID(as_uuid=True), nullable=True),
        )
        op.create_index("ix_takeoff_line_items_wage_rate_id", "takeoff_line_items", ["wage_rate_id"])
        op.create_foreign_key(
            "fk_takeoff_line_items_wage_rate_id",
            "takeoff_line_items",
            "wage_rates",
            ["wage_rate_id"],
            ["id"],
            ondelete="SET NULL",
        )
    if "labor_crew" not in cols:
        op.add_column(
            "takeoff_line_items",
            sa.Column("labor_crew", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("takeoff_line_items")}
    fks = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("takeoff_line_items")}
    indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("takeoff_line_items")}
    if "fk_takeoff_line_items_wage_rate_id" in fks:
        op.drop_constraint("fk_takeoff_line_items_wage_rate_id", "takeoff_line_items", type_="foreignkey")
    if "ix_takeoff_line_items_wage_rate_id" in indexes:
        op.drop_index("ix_takeoff_line_items_wage_rate_id", table_name="takeoff_line_items")
    if "wage_rate_id" in cols:
        op.drop_column("takeoff_line_items", "wage_rate_id")
    if "labor_crew" in cols:
        op.drop_column("takeoff_line_items", "labor_crew")
