"""Project-level RFIs and submittals (Procore-style tools).

Revision ID: 0009_project_rfis_submittals
Revises: 0008_active_project_external_id
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_project_rfis_submittals"
down_revision: Union[str, Sequence[str], None] = "0008_active_project_external_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rfis",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("ball_in_court", sa.String(200), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_impact", sa.Numeric(15, 2), nullable=True),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("official_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "number", name="uq_rfis_project_number"),
    )
    op.create_index("ix_rfis_project_id", "rfis", ["project_id"])
    op.create_index("ix_rfis_status", "rfis", ["status"])

    op.create_table(
        "submittals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("spec_section", sa.String(120), nullable=True),
        sa.Column("submittal_type", sa.String(120), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("ball_in_court", sa.String(200), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "number", name="uq_submittals_project_number"),
    )
    op.create_index("ix_submittals_project_id", "submittals", ["project_id"])
    op.create_index("ix_submittals_status", "submittals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_submittals_status", table_name="submittals")
    op.drop_index("ix_submittals_project_id", table_name="submittals")
    op.drop_table("submittals")
    op.drop_index("ix_rfis_status", table_name="rfis")
    op.drop_index("ix_rfis_project_id", table_name="rfis")
    op.drop_table("rfis")
