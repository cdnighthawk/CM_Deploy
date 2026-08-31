"""Per-user last seen and activity events for productivity tracking.

Revision ID: 0089_user_act
Revises: 0088_order_trk
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0089_user_act"
down_revision: Union[str, Sequence[str], None] = "0088_order_trk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_users_last_seen_at", "users", ["last_seen_at"])
    op.create_index("ix_users_last_login_at", "users", ["last_login_at"])

    op.create_table(
        "user_activity_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("path", sa.String(length=500), nullable=True),
        sa.Column("summary", sa.String(length=300), nullable=False),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_activity_events_user_id", "user_activity_events", ["user_id"])
    op.create_index("ix_user_activity_events_event_type", "user_activity_events", ["event_type"])
    op.create_index("ix_user_activity_events_created_at", "user_activity_events", ["created_at"])
    op.create_index(
        "ix_user_activity_events_user_created",
        "user_activity_events",
        ["user_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_activity_events_user_created", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_created_at", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_event_type", table_name="user_activity_events")
    op.drop_index("ix_user_activity_events_user_id", table_name="user_activity_events")
    op.drop_table("user_activity_events")
    op.drop_index("ix_users_last_login_at", table_name="users")
    op.drop_index("ix_users_last_seen_at", table_name="users")
    op.drop_column("users", "last_seen_at")
