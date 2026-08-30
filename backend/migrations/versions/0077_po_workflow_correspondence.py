"""Correspondence archive tables for Phase 1 file ingest.

Revision ID: 0077_corr_po
Revises: 0076_safety_docs
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0077_corr_po"
down_revision: Union[str, Sequence[str], None] = "0076_safety_docs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "correspondence_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("external_key", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("mailbox", sa.String(255), nullable=True),
        sa.Column("team_id", sa.String(120), nullable=True),
        sa.Column("channel_id", sa.String(120), nullable=True),
        sa.Column("default_project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["default_project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_type", "external_key", name="uq_correspondence_sources_type_key"),
    )
    op.create_index("ix_correspondence_sources_source_type", "correspondence_sources", ["source_type"])
    op.create_index("ix_correspondence_sources_default_project_id", "correspondence_sources", ["default_project_id"])

    op.create_table(
        "correspondence_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_type", sa.String(40), nullable=False, server_default="mailbox"),
        sa.Column("graph_message_id", sa.String(512), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("from_name", sa.String(255), nullable=True),
        sa.Column("from_email", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("storage_relpath", sa.String(1024), nullable=False),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("has_attachments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("attachment_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("filed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["correspondence_sources.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["filed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("graph_message_id"),
    )
    op.create_index("ix_correspondence_items_project_id", "correspondence_items", ["project_id"])
    op.create_index("ix_correspondence_items_source_id", "correspondence_items", ["source_id"])
    op.create_index("ix_correspondence_items_from_email", "correspondence_items", ["from_email"])
    op.create_index("ix_correspondence_items_sent_at", "correspondence_items", ["sent_at"])


def downgrade() -> None:
    op.drop_table("correspondence_items")
    op.drop_table("correspondence_sources")
