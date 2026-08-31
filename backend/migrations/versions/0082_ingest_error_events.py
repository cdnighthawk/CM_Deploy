"""Persist mass-ingest failures for the error tracker.

Revision ID: 0082_ingest_err
Revises: 0081_bid_loc
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0082_ingest_err"
down_revision: Union[str, Sequence[str], None] = "0081_bid_loc"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ingest_error_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=True),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="mass_ingest"),
        sa.Column("relative_path", sa.Text(), nullable=False, server_default=""),
        sa.Column("filename", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("kind", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_number", sa.String(length=40), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_note", sa.Text(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_error_events_batch_id", "ingest_error_events", ["batch_id"])
    op.create_index("ix_ingest_error_events_source", "ingest_error_events", ["source"])
    op.create_index("ix_ingest_error_events_project_id", "ingest_error_events", ["project_id"])
    op.create_index("ix_ingest_error_events_status", "ingest_error_events", ["status"])
    op.create_index("ix_ingest_error_events_batch_status", "ingest_error_events", ["batch_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_ingest_error_events_batch_status", table_name="ingest_error_events")
    op.drop_index("ix_ingest_error_events_status", table_name="ingest_error_events")
    op.drop_index("ix_ingest_error_events_project_id", table_name="ingest_error_events")
    op.drop_index("ix_ingest_error_events_source", table_name="ingest_error_events")
    op.drop_index("ix_ingest_error_events_batch_id", table_name="ingest_error_events")
    op.drop_table("ingest_error_events")
