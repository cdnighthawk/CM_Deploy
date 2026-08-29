"""Golden State / AGC San Diego weekly planroom leads.

Revision ID: 0070_golden_state_planroom_leads
Revises: 0069_field_daily_reports_photos
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0070_golden_state_planroom_leads"
down_revision: Union[str, Sequence[str], None] = "0069_field_daily_reports_photos"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "golden_state_planroom_leads",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("plan_number", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("bid_date", sa.Date(), nullable=True),
        sa.Column("bid_time", sa.String(40), nullable=True),
        sa.Column("addenda_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimate_high", sa.Numeric(16, 2), nullable=True),
        sa.Column("is_new", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("bid_date_changed", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("listing_week", sa.Date(), nullable=True),
        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("source", sa.String(60), nullable=False, server_default="ONLINE_PLAN_SERVICE"),
        sa.Column("crm_stage", sa.String(80), nullable=False, server_default="New Lead"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_gs_planroom_leads_location", "golden_state_planroom_leads", ["location"])
    op.create_index("ix_gs_planroom_leads_bid_date", "golden_state_planroom_leads", ["bid_date"])
    op.create_index("ix_gs_planroom_leads_is_new", "golden_state_planroom_leads", ["is_new"])
    op.create_index("ix_gs_planroom_leads_crm_stage", "golden_state_planroom_leads", ["crm_stage"])


def downgrade() -> None:
    op.drop_index("ix_gs_planroom_leads_crm_stage", table_name="golden_state_planroom_leads")
    op.drop_index("ix_gs_planroom_leads_is_new", table_name="golden_state_planroom_leads")
    op.drop_index("ix_gs_planroom_leads_bid_date", table_name="golden_state_planroom_leads")
    op.drop_index("ix_gs_planroom_leads_location", table_name="golden_state_planroom_leads")
    op.drop_table("golden_state_planroom_leads")
