"""Plan 7: daily pre-task safety plans (Appendix E).

Revision ID: 0075_daily_pretasks
Revises: 0074_ai_chat_sessions
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0075_daily_pretasks"
down_revision: Union[str, Sequence[str], None] = "0074_ai_chat_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_pretasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("crew_lead_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("daily_report_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_name", sa.String(length=255), nullable=False, server_default="DOCON, INC"),
        sa.Column("area_of_work", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        sa.Column("checklist", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("tasks", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("near_miss", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("near_miss_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("required_permits", sa.Text(), nullable=False, server_default=""),
        sa.Column("items_concerns", sa.Text(), nullable=False, server_default=""),
        sa.Column("quality_previous_day", sa.Text(), nullable=False, server_default=""),
        sa.Column("present_items_concerns", sa.Text(), nullable=False, server_default=""),
        sa.Column("attendees", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("supervisor_name", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("supervisor_signature", sa.Text(), nullable=False, server_default=""),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["crew_lead_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["daily_report_id"], ["daily_reports.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("project_id", "work_date", "crew_lead_user_id", name="uq_daily_pretasks_project_date_lead"),
        sa.UniqueConstraint("client_id", name="uq_daily_pretasks_client_id"),
    )
    op.create_index("ix_daily_pretasks_project_id", "daily_pretasks", ["project_id"])
    op.create_index("ix_daily_pretasks_work_date", "daily_pretasks", ["work_date"])
    op.create_index("ix_daily_pretasks_crew_lead_user_id", "daily_pretasks", ["crew_lead_user_id"])
    op.create_index("ix_daily_pretasks_daily_report_id", "daily_pretasks", ["daily_report_id"])
    op.create_index("ix_daily_pretasks_status", "daily_pretasks", ["status"])


def downgrade() -> None:
    op.drop_index("ix_daily_pretasks_status", table_name="daily_pretasks")
    op.drop_index("ix_daily_pretasks_daily_report_id", table_name="daily_pretasks")
    op.drop_index("ix_daily_pretasks_crew_lead_user_id", table_name="daily_pretasks")
    op.drop_index("ix_daily_pretasks_work_date", table_name="daily_pretasks")
    op.drop_index("ix_daily_pretasks_project_id", table_name="daily_pretasks")
    op.drop_table("daily_pretasks")
