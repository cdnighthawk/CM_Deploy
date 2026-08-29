"""Per-user Grok chat threads.

Revision ID: 0074_ai_chat_sessions
Revises: 0073_field_time_clock
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0074_ai_chat_sessions"
down_revision: Union[str, Sequence[str], None] = "0073_field_time_clock"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "ai_chat_sessions" not in tables:
        op.create_table(
            "ai_chat_sessions",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("mode", sa.String(length=64), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_chat_sessions_user_id", "ai_chat_sessions", ["user_id"], unique=False)
        op.create_index(
            "ix_ai_chat_sessions_user_updated",
            "ai_chat_sessions",
            ["user_id", "updated_at"],
            unique=False,
        )
    if "ai_chat_messages" not in tables:
        op.create_table(
            "ai_chat_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("attachments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("sort_index", sa.Integer(), nullable=False, server_default="0"),
            sa.ForeignKeyConstraint(["session_id"], ["ai_chat_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ai_chat_messages_session_id", "ai_chat_messages", ["session_id"], unique=False)
        op.create_index(
            "ix_ai_chat_messages_session_sort",
            "ai_chat_messages",
            ["session_id", "sort_index"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "ai_chat_messages" in tables:
        op.drop_index("ix_ai_chat_messages_session_sort", table_name="ai_chat_messages")
        op.drop_index("ix_ai_chat_messages_session_id", table_name="ai_chat_messages")
        op.drop_table("ai_chat_messages")
    if "ai_chat_sessions" in tables:
        op.drop_index("ix_ai_chat_sessions_user_updated", table_name="ai_chat_sessions")
        op.drop_index("ix_ai_chat_sessions_user_id", table_name="ai_chat_sessions")
        op.drop_table("ai_chat_sessions")
