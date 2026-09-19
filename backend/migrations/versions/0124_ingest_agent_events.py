"""Persist ACCDocs/Forma agent status events for the CM Ingest panel.

Revision ID: 0124_ingest_evt
Revises: 0123_openings
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0124_ingest_evt"
down_revision: Union[str, Sequence[str], None] = "0123_openings"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    if "ingest_agent_events" in _tables(bind):
        return
    op.create_table(
        "ingest_agent_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="accdocs"),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("lead_estimate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_number", sa.String(length=40), nullable=True),
        sa.Column("folder_name", sa.String(length=255), nullable=True),
        sa.Column("uploaded_count", sa.Integer(), nullable=True),
        sa.Column("host", sa.String(length=120), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["lead_estimate_id"], ["lead_estimates.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingest_agent_events_organization_id", "ingest_agent_events", ["organization_id"])
    op.create_index("ix_ingest_agent_events_event_type", "ingest_agent_events", ["event_type"])
    op.create_index("ix_ingest_agent_events_source", "ingest_agent_events", ["source"])
    op.create_index("ix_ingest_agent_events_occurred_at", "ingest_agent_events", ["occurred_at"])
    op.create_index("ix_ingest_agent_events_project_id", "ingest_agent_events", ["project_id"])
    op.create_index("ix_ingest_agent_events_lead_estimate_id", "ingest_agent_events", ["lead_estimate_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if "ingest_agent_events" not in _tables(bind):
        return
    op.drop_index("ix_ingest_agent_events_lead_estimate_id", table_name="ingest_agent_events")
    op.drop_index("ix_ingest_agent_events_project_id", table_name="ingest_agent_events")
    op.drop_index("ix_ingest_agent_events_occurred_at", table_name="ingest_agent_events")
    op.drop_index("ix_ingest_agent_events_source", table_name="ingest_agent_events")
    op.drop_index("ix_ingest_agent_events_event_type", table_name="ingest_agent_events")
    op.drop_index("ix_ingest_agent_events_organization_id", table_name="ingest_agent_events")
    op.drop_table("ingest_agent_events")
