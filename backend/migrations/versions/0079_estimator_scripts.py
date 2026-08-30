"""Estimator script catalog + per-estimate bid scope.

Revision ID: 0079_est_scripts
Revises: 0078_ai_wf
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0079_est_scripts"
down_revision: Union[str, Sequence[str], None] = "0078_ai_wf"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "estimator_scripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("script_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("spec_prefixes", postgresql.JSONB(), nullable=True),
        sa.Column("applies_when", sa.String(40), nullable=False, server_default="always"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("script_key"),
    )
    op.create_index("ix_estimator_scripts_kind", "estimator_scripts", ["kind"])

    op.create_table(
        "estimator_standard_specs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("spec_code", sa.String(20), nullable=False),
        sa.Column("spec_title", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("spec_code", name="uq_estimator_standard_specs_code"),
    )

    op.create_table(
        "estimate_bid_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source", sa.String(40), nullable=False, server_default="standard"),
        sa.Column("bid_package_label", sa.String(200), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("estimate_id"),
    )
    op.create_index("ix_estimate_bid_scopes_status", "estimate_bid_scopes", ["status"])

    op.create_table(
        "estimate_bid_scope_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("spec_code", sa.String(20), nullable=False),
        sa.Column("spec_title", sa.String(200), nullable=False),
        sa.Column("script_key", sa.String(80), nullable=True),
        sa.Column("included", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("item_source", sa.String(40), nullable=False, server_default="standard"),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("workflow_instance_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["scope_id"], ["estimate_bid_scopes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_instance_id"], ["workflow_instances.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_estimate_bid_scope_items_scope_id", "estimate_bid_scope_items", ["scope_id"])


def downgrade() -> None:
    op.drop_table("estimate_bid_scope_items")
    op.drop_table("estimate_bid_scopes")
    op.drop_table("estimator_standard_specs")
    op.drop_index("ix_estimator_scripts_kind", table_name="estimator_scripts")
    op.drop_table("estimator_scripts")
