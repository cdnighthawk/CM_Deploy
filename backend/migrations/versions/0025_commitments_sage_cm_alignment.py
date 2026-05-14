"""Commitments (PO / subcontract), line items, bill allocations (Sage CM alignment).

Revision ID: 0025_commitments
Revises: 0024_hr_pay_docs
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0025_commitments"
down_revision: Union[str, Sequence[str], None] = "0024_hr_pay_docs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

commitment_kind = postgresql.ENUM(
    "purchase_order",
    "subcontract",
    name="commitment_kind",
    create_type=False,
)
commitment_status = postgresql.ENUM(
    "draft",
    "pending_submission",
    "pending",
    "not_approved",
    "approved",
    name="commitment_status",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    commitment_kind.create(bind, checkfirst=True)
    commitment_status.create(bind, checkfirst=True)

    op.create_table(
        "commitments",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commitment_kind", commitment_kind, nullable=False),
        sa.Column("reference_number", sa.String(80), nullable=True),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", commitment_status, nullable=False, server_default="draft"),
        sa.Column("status_effective_date", sa.Date(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("workflow_rule_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retention_percentage", sa.Numeric(5, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("total_amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("rfp_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vendor_company_id"], ["companies.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rfp_id"], ["rfps.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_commitments_project_id", "commitments", ["project_id"], unique=False)
    op.create_index("ix_commitments_vendor_company_id", "commitments", ["vendor_company_id"], unique=False)
    op.create_index("ix_commitments_status", "commitments", ["status"], unique=False)
    op.create_index("ix_commitments_kind_status", "commitments", ["commitment_kind", "status"], unique=False)

    op.create_table(
        "commitment_line_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("commitment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(50), nullable=False, server_default="EA"),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("tax_code", sa.String(40), nullable=True),
        sa.Column("takeoff_line_item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["takeoff_line_item_id"], ["takeoff_line_items.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_commitment_line_items_commitment_id",
        "commitment_line_items",
        ["commitment_id"],
        unique=False,
    )
    op.create_index(
        "ix_commitment_line_items_cost_code_id",
        "commitment_line_items",
        ["cost_code_id"],
        unique=False,
    )

    op.create_table(
        "commitment_bill_allocations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("commitment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vendor_bill_ref", sa.String(120), nullable=False),
        sa.Column("allocated_amount", sa.Numeric(15, 2), nullable=False),
        sa.Column("billed_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_commitment_bill_allocations_commitment_id",
        "commitment_bill_allocations",
        ["commitment_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_commitment_bill_allocations_commitment_id", table_name="commitment_bill_allocations")
    op.drop_table("commitment_bill_allocations")

    op.drop_index("ix_commitment_line_items_cost_code_id", table_name="commitment_line_items")
    op.drop_index("ix_commitment_line_items_commitment_id", table_name="commitment_line_items")
    op.drop_table("commitment_line_items")

    op.drop_index("ix_commitments_kind_status", table_name="commitments")
    op.drop_index("ix_commitments_status", table_name="commitments")
    op.drop_index("ix_commitments_vendor_company_id", table_name="commitments")
    op.drop_index("ix_commitments_project_id", table_name="commitments")
    op.drop_table("commitments")

    bind = op.get_bind()
    commitment_status.drop(bind, checkfirst=True)
    commitment_kind.drop(bind, checkfirst=True)
