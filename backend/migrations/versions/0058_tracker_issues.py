"""Unified issues tracker table.

Revision ID: 0058_tracker_issues
Revises: 0057_independent_estimates
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0058_tracker_issues"
down_revision: Union[str, Sequence[str], None] = "0057_independent_estimates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tracker_issues",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="Minor"),
        sa.Column("status", sa.String(40), nullable=False, server_default="New"),
        sa.Column("trade", sa.String(80), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cbc_citation", sa.String(200), nullable=True),
        sa.Column("cost_impact", sa.Numeric(15, 2), nullable=True),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("assignee_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sheet_number", sa.String(50), nullable=True),
        sa.Column("linked_rfi_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("linked_change_order_id", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("source_type", "source_id", name="uq_tracker_issues_source"),
    )
    op.create_index("ix_tracker_issues_project_id", "tracker_issues", ["project_id"])
    op.create_index("ix_tracker_issues_status", "tracker_issues", ["status"])
    op.create_index("ix_tracker_issues_severity", "tracker_issues", ["severity"])
    op.create_index("ix_tracker_issues_source_type", "tracker_issues", ["source_type"])
    op.create_index("ix_tracker_issues_source_id", "tracker_issues", ["source_id"])

    op.create_table(
        "tracker_issue_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["issue_id"], ["tracker_issues.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_tracker_issue_events_issue_id", "tracker_issue_events", ["issue_id"])


def downgrade() -> None:
    op.drop_index("ix_tracker_issue_events_issue_id", table_name="tracker_issue_events")
    op.drop_table("tracker_issue_events")
    op.drop_index("ix_tracker_issues_source_id", table_name="tracker_issues")
    op.drop_index("ix_tracker_issues_source_type", table_name="tracker_issues")
    op.drop_index("ix_tracker_issues_severity", table_name="tracker_issues")
    op.drop_index("ix_tracker_issues_status", table_name="tracker_issues")
    op.drop_index("ix_tracker_issues_project_id", table_name="tracker_issues")
    op.drop_table("tracker_issues")
