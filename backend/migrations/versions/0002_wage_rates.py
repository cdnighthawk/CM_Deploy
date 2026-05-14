"""Wage rates reference table.

Revision ID: 0002_wage_rates
Revises: 0001_phase1_core
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_wage_rates"
down_revision: Union[str, Sequence[str], None] = "0001_phase1_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "wage_rates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("state", sa.String(80), nullable=False),
        sa.Column(
            "sub_area",
            sa.String(80),
            nullable=False,
            server_default=sa.text("''"),
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("trade", sa.String(120), nullable=False),
        sa.Column("basic_hourly_rate", sa.Numeric(10, 4), nullable=True),
        sa.Column("health_welfare", sa.Numeric(10, 4), nullable=True),
        sa.Column("pension", sa.Numeric(10, 4), nullable=True),
        sa.Column("vacation_holiday", sa.Numeric(10, 4), nullable=True),
        sa.Column("other_payments", sa.Numeric(10, 4), nullable=True),
        sa.Column("training", sa.Numeric(10, 4), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("is_assumed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "state",
            "sub_area",
            "year",
            "trade",
            name="uq_wage_rates_state_sub_area_year_trade",
        ),
    )
    op.create_index("ix_wage_rates_state", "wage_rates", ["state"])
    op.create_index("ix_wage_rates_year", "wage_rates", ["year"])
    op.create_index("ix_wage_rates_trade", "wage_rates", ["trade"])


def downgrade() -> None:
    op.drop_table("wage_rates")
