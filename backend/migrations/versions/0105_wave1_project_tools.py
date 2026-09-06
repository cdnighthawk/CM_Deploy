"""Wave 1 project-tool completeness: CPR/CO/SCO/POCO/meeting/sub-invoice columns.

Revision ID: 0105_w1_tools
Revises: 0103_hiring

0104_tx_sync_id is a local-only revision (untracked). Render's flask db upgrade
could not find that parent, so the Wave 1 create pages never left the previous
deploy — production 404s.

Render uses psycopg3, which rejects more than one SQL command per execute().
Keep each ALTER / DO block as its own statement.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0105_w1_tools"
down_revision: Union[str, Sequence[str], None] = "0103_hiring"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _exec(sql: str) -> None:
    op.execute(sa.text(sql.strip()))


def upgrade() -> None:
    _exec(
        """
        ALTER TABLE IF EXISTS change_proposal_requests
            ADD COLUMN IF NOT EXISTS origin varchar(40) DEFAULT 'other'
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS change_proposal_requests
            ADD COLUMN IF NOT EXISTS source_tm_ticket_id uuid
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS change_proposal_requests
            ADD COLUMN IF NOT EXISTS source_rfi_id uuid
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS owner_change_orders
            ADD COLUMN IF NOT EXISTS approved_revises_contract boolean NOT NULL DEFAULT false
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS owner_change_orders
            ADD COLUMN IF NOT EXISTS contract_value_applied numeric(15, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS owner_change_orders
            ADD COLUMN IF NOT EXISTS source_tm_ticket_id uuid
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS owner_change_orders
            ADD COLUMN IF NOT EXISTS gc_company_id uuid
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS subcontract_change_orders
            ADD COLUMN IF NOT EXISTS value_applied numeric(15, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS purchase_order_change_orders
            ADD COLUMN IF NOT EXISTS applied boolean NOT NULL DEFAULT false
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS purchase_order_change_orders
            ADD COLUMN IF NOT EXISTS amount_applied numeric(15, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS purchase_order_change_orders
            ADD COLUMN IF NOT EXISTS line_snapshot jsonb NOT NULL DEFAULT '[]'::jsonb
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS sub_invoices
            ADD COLUMN IF NOT EXISTS period_start date
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS sub_invoices
            ADD COLUMN IF NOT EXISTS period_end date
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS sub_invoices
            ADD COLUMN IF NOT EXISTS retainage_pct numeric(5, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS sub_invoices
            ADD COLUMN IF NOT EXISTS this_period numeric(15, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS sub_invoices
            ADD COLUMN IF NOT EXISTS previous_to_date numeric(15, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS sub_invoices
            ADD COLUMN IF NOT EXISTS amount_due numeric(15, 2)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS meetings
            ADD COLUMN IF NOT EXISTS meeting_type varchar(40) DEFAULT 'other'
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS meetings
            ADD COLUMN IF NOT EXISTS start_time varchar(16)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS meetings
            ADD COLUMN IF NOT EXISTS end_time varchar(16)
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS meetings
            ADD COLUMN IF NOT EXISTS facilitator_user_id uuid
        """
    )
    _exec(
        """
        ALTER TABLE IF EXISTS meetings
            ADD COLUMN IF NOT EXISTS minutes text
        """
    )
    _exec(
        """
        DO $$ BEGIN
            ALTER TABLE change_proposal_requests
                ADD CONSTRAINT fk_cpr_source_rfi
                FOREIGN KEY (source_rfi_id) REFERENCES rfis(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
                  WHEN undefined_table THEN NULL;
                  WHEN undefined_column THEN NULL;
        END $$
        """
    )
    _exec(
        """
        DO $$ BEGIN
            ALTER TABLE owner_change_orders
                ADD CONSTRAINT fk_oco_gc_company
                FOREIGN KEY (gc_company_id) REFERENCES companies(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
                  WHEN undefined_table THEN NULL;
                  WHEN undefined_column THEN NULL;
        END $$
        """
    )
    _exec(
        """
        DO $$ BEGIN
            ALTER TABLE meetings
                ADD CONSTRAINT fk_meetings_facilitator
                FOREIGN KEY (facilitator_user_id) REFERENCES users(id) ON DELETE SET NULL;
        EXCEPTION WHEN duplicate_object THEN NULL;
                  WHEN undefined_table THEN NULL;
                  WHEN undefined_column THEN NULL;
        END $$
        """
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
