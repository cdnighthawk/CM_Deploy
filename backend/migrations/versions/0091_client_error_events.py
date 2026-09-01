"""Persist website connection failures and similar client/server errors.

Revision ID: 0091_client_err
Revises: 0090_rfp_quote
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0091_client_err"
down_revision: Union[str, Sequence[str], None] = "0090_rfp_quote"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "client_error_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="browser"),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=True),
        sa.Column("method", sa.String(length=10), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("page", sa.String(length=500), nullable=True),
        sa.Column("fingerprint", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_client_error_events_user_id", "client_error_events", ["user_id"])
    op.create_index("ix_client_error_events_source", "client_error_events", ["source"])
    op.create_index("ix_client_error_events_kind", "client_error_events", ["kind"])
    op.create_index("ix_client_error_events_fingerprint", "client_error_events", ["fingerprint"])
    op.create_index("ix_client_error_events_occurred_at", "client_error_events", ["occurred_at"])
    op.create_index("ix_client_error_events_created_at", "client_error_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_client_error_events_created_at", table_name="client_error_events")
    op.drop_index("ix_client_error_events_occurred_at", table_name="client_error_events")
    op.drop_index("ix_client_error_events_fingerprint", table_name="client_error_events")
    op.drop_index("ix_client_error_events_kind", table_name="client_error_events")
    op.drop_index("ix_client_error_events_source", table_name="client_error_events")
    op.drop_index("ix_client_error_events_user_id", table_name="client_error_events")
    op.drop_table("client_error_events")
