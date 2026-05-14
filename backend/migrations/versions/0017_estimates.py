"""Estimate headers and line items (Plan 4)."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017_estimates"
down_revision: Union[str, Sequence[str], None] = "0016_takeoff_project_scope"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "estimates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lead_estimate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="Draft"),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("total", sa.Numeric(15, 2), nullable=True),
        sa.ForeignKeyConstraint(["lead_estimate_id"], ["lead_estimates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_estimates_lead_estimate_id", "estimates", ["lead_estimate_id"], unique=False)
    op.create_index("ix_estimates_project_id", "estimates", ["project_id"], unique=False)

    op.create_table(
        "estimate_line_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("takeoff_line_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("markup_percentage", sa.Numeric(7, 4), nullable=True),
        sa.Column("vendor_quote", sa.Numeric(15, 4), nullable=True),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["takeoff_line_item_id"], ["takeoff_line_items.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_estimate_line_items_estimate_id", "estimate_line_items", ["estimate_id"], unique=False)
    op.create_index(
        "ix_estimate_line_items_takeoff_line_item_id", "estimate_line_items", ["takeoff_line_item_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_estimate_line_items_takeoff_line_item_id", table_name="estimate_line_items")
    op.drop_index("ix_estimate_line_items_estimate_id", table_name="estimate_line_items")
    op.drop_table("estimate_line_items")
    op.drop_index("ix_estimates_project_id", table_name="estimates")
    op.drop_index("ix_estimates_lead_estimate_id", table_name="estimates")
    op.drop_table("estimates")
