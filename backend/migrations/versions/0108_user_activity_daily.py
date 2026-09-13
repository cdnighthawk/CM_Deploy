"""Daily productivity rollups and 1-year activity retention support.

Revision ID: 0108_act_daily
Revises: 0107_drop_crew_punch
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0108_act_daily"
down_revision: Union[str, Sequence[str], None] = "0107_drop_crew_punch"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("activity_heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "user_activity_daily",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_date", sa.Date(), nullable=False),
        sa.Column("active_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("page_views", sa.Integer(), server_default="0", nullable=False),
        sa.Column("api_writes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("logins", sa.Integer(), server_default="0", nullable=False),
        sa.Column("sessions", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "activity_date", name="uq_user_activity_daily_user_date"),
    )
    op.create_index("ix_user_activity_daily_user_id", "user_activity_daily", ["user_id"])
    op.create_index("ix_user_activity_daily_activity_date", "user_activity_daily", ["activity_date"])


def downgrade() -> None:
    op.drop_index("ix_user_activity_daily_activity_date", table_name="user_activity_daily")
    op.drop_index("ix_user_activity_daily_user_id", table_name="user_activity_daily")
    op.drop_table("user_activity_daily")
    op.drop_column("users", "activity_heartbeat_at")
