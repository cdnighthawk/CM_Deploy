"""Wave 1 project-tool completeness: CPR/CO/SCO/POCO/meeting/sub-invoice columns.

Revision ID: 0105_w1_tools
Revises: 0103_hiring

0104_tx_sync_id is a local-only revision (untracked). Render's flask db upgrade
could not find that parent, so the Wave 1 create pages never left the previous
deploy — production 404s.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0105_w1_tools"
down_revision: Union[str, Sequence[str], None] = "0103_hiring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _col_names(insp, table: str) -> set[str]:
    if table not in set(insp.get_table_names()):
        return set()
    return {c["name"] for c in insp.get_columns(table)}


def _fk_names(insp, table: str) -> set[str]:
    if table not in set(insp.get_table_names()):
        return set()
    return {fk.get("name") for fk in insp.get_foreign_keys(table) if fk.get("name")}


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    uuid_col = postgresql.UUID(as_uuid=True)

    if "change_proposal_requests" in tables:
        cols = _col_names(insp, "change_proposal_requests")
        fks = _fk_names(insp, "change_proposal_requests")
        if "origin" not in cols:
            op.add_column(
                "change_proposal_requests",
                sa.Column("origin", sa.String(length=40), nullable=True, server_default=sa.text("'other'")),
            )
        if "source_tm_ticket_id" not in cols:
            op.add_column(
                "change_proposal_requests",
                sa.Column("source_tm_ticket_id", uuid_col, nullable=True),
            )
        if "source_rfi_id" not in cols:
            op.add_column(
                "change_proposal_requests",
                sa.Column("source_rfi_id", uuid_col, nullable=True),
            )
        if "fk_cpr_source_rfi" not in fks and "rfis" in tables:
            op.create_foreign_key(
                "fk_cpr_source_rfi",
                "change_proposal_requests",
                "rfis",
                ["source_rfi_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "owner_change_orders" in tables:
        cols = _col_names(insp, "owner_change_orders")
        fks = _fk_names(insp, "owner_change_orders")
        if "approved_revises_contract" not in cols:
            op.add_column(
                "owner_change_orders",
                sa.Column("approved_revises_contract", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if "contract_value_applied" not in cols:
            op.add_column(
                "owner_change_orders",
                sa.Column("contract_value_applied", sa.Numeric(15, 2), nullable=True),
            )
        if "source_tm_ticket_id" not in cols:
            op.add_column(
                "owner_change_orders",
                sa.Column("source_tm_ticket_id", uuid_col, nullable=True),
            )
        if "gc_company_id" not in cols:
            op.add_column(
                "owner_change_orders",
                sa.Column("gc_company_id", uuid_col, nullable=True),
            )
        if "fk_oco_gc_company" not in fks and "companies" in tables:
            op.create_foreign_key(
                "fk_oco_gc_company",
                "owner_change_orders",
                "companies",
                ["gc_company_id"],
                ["id"],
                ondelete="SET NULL",
            )

    if "subcontract_change_orders" in tables:
        cols = _col_names(insp, "subcontract_change_orders")
        if "value_applied" not in cols:
            op.add_column(
                "subcontract_change_orders",
                sa.Column("value_applied", sa.Numeric(15, 2), nullable=True),
            )

    if "purchase_order_change_orders" in tables:
        cols = _col_names(insp, "purchase_order_change_orders")
        if "applied" not in cols:
            op.add_column(
                "purchase_order_change_orders",
                sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
            )
        if "amount_applied" not in cols:
            op.add_column(
                "purchase_order_change_orders",
                sa.Column("amount_applied", sa.Numeric(15, 2), nullable=True),
            )
        if "line_snapshot" not in cols:
            op.add_column(
                "purchase_order_change_orders",
                sa.Column("line_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
            )

    if "sub_invoices" in tables:
        cols = _col_names(insp, "sub_invoices")
        for name, col in (
            ("period_start", sa.Column("period_start", sa.Date(), nullable=True)),
            ("period_end", sa.Column("period_end", sa.Date(), nullable=True)),
            ("retainage_pct", sa.Column("retainage_pct", sa.Numeric(5, 2), nullable=True)),
            ("this_period", sa.Column("this_period", sa.Numeric(15, 2), nullable=True)),
            ("previous_to_date", sa.Column("previous_to_date", sa.Numeric(15, 2), nullable=True)),
            ("amount_due", sa.Column("amount_due", sa.Numeric(15, 2), nullable=True)),
        ):
            if name not in cols:
                op.add_column("sub_invoices", col)

    if "meetings" in tables:
        cols = _col_names(insp, "meetings")
        fks = _fk_names(insp, "meetings")
        if "meeting_type" not in cols:
            op.add_column(
                "meetings",
                sa.Column("meeting_type", sa.String(length=40), nullable=True, server_default=sa.text("'other'")),
            )
        if "start_time" not in cols:
            op.add_column("meetings", sa.Column("start_time", sa.String(length=16), nullable=True))
        if "end_time" not in cols:
            op.add_column("meetings", sa.Column("end_time", sa.String(length=16), nullable=True))
        if "facilitator_user_id" not in cols:
            op.add_column("meetings", sa.Column("facilitator_user_id", uuid_col, nullable=True))
        if "minutes" not in cols:
            op.add_column("meetings", sa.Column("minutes", sa.Text(), nullable=True))
        if "fk_meetings_facilitator" not in fks and "users" in tables:
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
