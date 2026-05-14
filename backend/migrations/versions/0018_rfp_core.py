"""RFP tables (Plan 5)."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0018_rfp_core"
down_revision: Union[str, Sequence[str], None] = "0017_estimates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rfps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("lead_estimate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="Draft"),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("public_token", sa.String(length=64), nullable=False),
        sa.ForeignKeyConstraint(["lead_estimate_id"], ["lead_estimates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rfps_lead_estimate_id", "rfps", ["lead_estimate_id"], unique=False)
    op.create_index("ix_rfps_project_id", "rfps", ["project_id"], unique=False)
    op.create_index("ix_rfps_public_token", "rfps", ["public_token"], unique=True)

    op.create_table(
        "rfp_line_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rfp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=50), nullable=False, server_default="EA"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["rfp_id"], ["rfps.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rfp_line_items_rfp_id", "rfp_line_items", ["rfp_id"], unique=False)

    op.create_table(
        "rfp_vendor_quotes",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("rfp_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_label", sa.String(length=255), nullable=False, server_default="Vendor"),
        sa.Column("line_prices", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["rfp_id"], ["rfps.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rfp_vendor_quotes_rfp_id", "rfp_vendor_quotes", ["rfp_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_rfp_vendor_quotes_rfp_id", table_name="rfp_vendor_quotes")
    op.drop_table("rfp_vendor_quotes")
    op.drop_index("ix_rfp_line_items_rfp_id", table_name="rfp_line_items")
    op.drop_table("rfp_line_items")
    op.drop_index("ix_rfps_public_token", table_name="rfps")
    op.drop_index("ix_rfps_project_id", table_name="rfps")
    op.drop_index("ix_rfps_lead_estimate_id", table_name="rfps")
    op.drop_table("rfps")
