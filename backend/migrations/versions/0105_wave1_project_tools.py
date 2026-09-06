"""Wave 1 project-tool completeness: CPR/CO/SCO/POCO/meeting/sub-invoice columns.

Revision ID: 0105_w1_tools
Revises: 0104_tx_sync_id
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0105_w1_tools"
down_revision: Union[str, Sequence[str], None] = "0104_tx_sync_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "change_proposal_requests",
        sa.Column("origin", sa.String(length=40), nullable=True, server_default="other"),
    )
    op.add_column(
        "change_proposal_requests",
        sa.Column("source_tm_ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "change_proposal_requests",
        sa.Column("source_rfi_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_cpr_source_rfi",
        "change_proposal_requests",
        "rfis",
        ["source_rfi_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "owner_change_orders",
        sa.Column("approved_revises_contract", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "owner_change_orders",
        sa.Column("contract_value_applied", sa.Numeric(15, 2), nullable=True),
    )
    op.add_column(
        "owner_change_orders",
        sa.Column("source_tm_ticket_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "owner_change_orders",
        sa.Column("gc_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_oco_gc_company",
        "owner_change_orders",
        "companies",
        ["gc_company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column(
        "subcontract_change_orders",
        sa.Column("value_applied", sa.Numeric(15, 2), nullable=True),
    )

    op.add_column(
        "purchase_order_change_orders",
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "purchase_order_change_orders",
        sa.Column("amount_applied", sa.Numeric(15, 2), nullable=True),
    )
    op.add_column(
        "purchase_order_change_orders",
        sa.Column("line_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )

    op.add_column("sub_invoices", sa.Column("period_start", sa.Date(), nullable=True))
    op.add_column("sub_invoices", sa.Column("period_end", sa.Date(), nullable=True))
    op.add_column("sub_invoices", sa.Column("retainage_pct", sa.Numeric(5, 2), nullable=True))
    op.add_column("sub_invoices", sa.Column("this_period", sa.Numeric(15, 2), nullable=True))
    op.add_column("sub_invoices", sa.Column("previous_to_date", sa.Numeric(15, 2), nullable=True))
    op.add_column("sub_invoices", sa.Column("amount_due", sa.Numeric(15, 2), nullable=True))

    op.add_column("meetings", sa.Column("meeting_type", sa.String(length=40), nullable=True, server_default="other"))
    op.add_column("meetings", sa.Column("start_time", sa.String(length=16), nullable=True))
    op.add_column("meetings", sa.Column("end_time", sa.String(length=16), nullable=True))
    op.add_column("meetings", sa.Column("facilitator_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("meetings", sa.Column("minutes", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_meetings_facilitator",
        "meetings",
        "users",
        ["facilitator_user_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_meetings_facilitator", "meetings", type_="foreignkey")
    op.drop_column("meetings", "minutes")
    op.drop_column("meetings", "facilitator_user_id")
    op.drop_column("meetings", "end_time")
    op.drop_column("meetings", "start_time")
    op.drop_column("meetings", "meeting_type")

    op.drop_column("sub_invoices", "amount_due")
    op.drop_column("sub_invoices", "previous_to_date")
    op.drop_column("sub_invoices", "this_period")
    op.drop_column("sub_invoices", "retainage_pct")
    op.drop_column("sub_invoices", "period_end")
    op.drop_column("sub_invoices", "period_start")

    op.drop_column("purchase_order_change_orders", "line_snapshot")
    op.drop_column("purchase_order_change_orders", "amount_applied")
    op.drop_column("purchase_order_change_orders", "applied")

    op.drop_column("subcontract_change_orders", "value_applied")

    op.drop_constraint("fk_oco_gc_company", "owner_change_orders", type_="foreignkey")
    op.drop_column("owner_change_orders", "gc_company_id")
    op.drop_column("owner_change_orders", "source_tm_ticket_id")
    op.drop_column("owner_change_orders", "contract_value_applied")
    op.drop_column("owner_change_orders", "approved_revises_contract")

    op.drop_constraint("fk_cpr_source_rfi", "change_proposal_requests", type_="foreignkey")
    op.drop_column("change_proposal_requests", "source_rfi_id")
    op.drop_column("change_proposal_requests", "source_tm_ticket_id")
    op.drop_column("change_proposal_requests", "origin")
