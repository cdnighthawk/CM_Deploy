"""takeoff_line_items - unified estimate / takeoff lines per lead estimate.

Revision ID: 0010_takeoff_line_items
Revises: 0009_project_rfis_submittals
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_takeoff_line_items"
down_revision: Union[str, Sequence[str], None] = "0009_project_rfis_submittals"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "takeoff_line_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lead_estimate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lead_estimates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("section", sa.String(120), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(50), nullable=False, server_default="EA"),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("extended_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column(
            "cost_type",
            sa.String(20),
            nullable=False,
            server_default="M",
            comment="L labor, M material, E equipment, S subcontract, O other",
        ),
        sa.Column("job_cost_code", sa.String(60), nullable=True),
        sa.Column("job_cost_code_description", sa.String(500), nullable=True),
        sa.Column("job_cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("measurement_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(40), nullable=True),
        sa.Column("version", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_takeoff_line_items_lead_estimate_id", "takeoff_line_items", ["lead_estimate_id"])
    op.create_index("ix_takeoff_line_items_project_id", "takeoff_line_items", ["project_id"])
    op.create_index("ix_takeoff_line_items_section", "takeoff_line_items", ["section"])
    op.create_index("ix_takeoff_line_items_job_cost_code", "takeoff_line_items", ["job_cost_code"])
    op.create_index("ix_takeoff_line_items_drawing_id", "takeoff_line_items", ["drawing_id"])


def downgrade() -> None:
    op.drop_index("ix_takeoff_line_items_drawing_id", table_name="takeoff_line_items")
    op.drop_index("ix_takeoff_line_items_job_cost_code", table_name="takeoff_line_items")
    op.drop_index("ix_takeoff_line_items_section", table_name="takeoff_line_items")
    op.drop_index("ix_takeoff_line_items_project_id", table_name="takeoff_line_items")
    op.drop_index("ix_takeoff_line_items_lead_estimate_id", table_name="takeoff_line_items")
    op.drop_table("takeoff_line_items")
