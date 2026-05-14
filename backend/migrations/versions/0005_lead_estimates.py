"""Lead estimates from BuildingConnected CSV export.

Revision ID: 0005_lead_estimates
Revises: 0004_sales_tax_rates
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_lead_estimates"
down_revision: Union[str, Sequence[str], None] = "0004_sales_tax_rates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "lead_estimates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("external_id", sa.String(64), nullable=False),
        sa.Column("external_parent_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(500), nullable=True),
        sa.Column("number", sa.String(120), nullable=True),
        sa.Column("trade_name", sa.String(255), nullable=True),
        sa.Column("submission_state", sa.String(60), nullable=True),
        sa.Column("outcome", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bc_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("bc_created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_archived", sa.Boolean(), nullable=True),
        sa.Column("final_value", sa.Numeric(15, 2), nullable=True),
        sa.Column("additional_info", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("architect", sa.String(500), nullable=True),
        sa.Column("average_crew_size", sa.Integer(), nullable=True),
        sa.Column("bid", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("client_values", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("competitors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("contract_duration", sa.Integer(), nullable=True),
        sa.Column("contract_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("custom_tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("decline_reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("default_currency", sa.String(3), nullable=True),
        sa.Column("engineer", sa.String(500), nullable=True),
        sa.Column("estimating_hours", sa.Numeric(10, 2), nullable=True),
        sa.Column("expected_finish_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expected_start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fee_percentage", sa.Numeric(7, 4), nullable=True),
        sa.Column("follow_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("group_children", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("invited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_nda_required", sa.Boolean(), nullable=True),
        sa.Column("is_parent", sa.Boolean(), nullable=True),
        sa.Column("is_sealed_bidding", sa.Boolean(), nullable=True),
        sa.Column("job_walk_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("location", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("market_sector", sa.String(120), nullable=True),
        sa.Column("members", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("owning_office_id", sa.String(64), nullable=True),
        sa.Column("priority", sa.String(60), nullable=True),
        sa.Column("profit_margin", sa.Numeric(7, 4), nullable=True),
        sa.Column("project_information", sa.Text(), nullable=True),
        sa.Column("project_is_public", sa.Boolean(), nullable=True),
        sa.Column("project_size", sa.Numeric(15, 2), nullable=True),
        sa.Column("property_owner", sa.String(500), nullable=True),
        sa.Column("property_tenant", sa.String(500), nullable=True),
        sa.Column("request_type", sa.String(60), nullable=True),
        sa.Column("rfis_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rom", sa.Numeric(15, 2), nullable=True),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("trade_specific_instructions", sa.Text(), nullable=True),
        sa.Column("win_probability", sa.Numeric(5, 4), nullable=True),
        sa.Column("workflow_bucket", sa.String(120), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("external_id", name="uq_lead_estimates_external_id"),
    )
    op.create_index("ix_lead_estimates_external_parent_id", "lead_estimates", ["external_parent_id"])
    op.create_index("ix_lead_estimates_trade_name", "lead_estimates", ["trade_name"])
    op.create_index("ix_lead_estimates_submission_state", "lead_estimates", ["submission_state"])
    op.create_index("ix_lead_estimates_source", "lead_estimates", ["source"])
    op.create_index("ix_lead_estimates_workflow_bucket", "lead_estimates", ["workflow_bucket"])
    op.create_index("ix_lead_estimates_due_at", "lead_estimates", ["due_at"])
    op.create_index("ix_lead_estimates_bc_updated_at", "lead_estimates", ["bc_updated_at"])


def downgrade() -> None:
    op.drop_table("lead_estimates")
