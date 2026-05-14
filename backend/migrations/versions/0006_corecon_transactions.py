"""Corecon ERP transaction-details unified table.

Revision ID: 0006_corecon_transactions
Revises: 0005_lead_estimates
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_corecon_transactions"
down_revision: Union[str, Sequence[str], None] = "0005_lead_estimates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "corecon_transactions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),

        sa.Column("source_file", sa.String(255), nullable=True),
        sa.Column("raw_row", postgresql.JSONB(astext_type=sa.Text()), nullable=True),

        sa.Column("corecon_id", sa.String(64), nullable=True),

        sa.Column("transaction_item_source", sa.String(80), nullable=True),
        sa.Column("transaction_source", sa.String(60), nullable=False),
        sa.Column("transaction_category_level_1", sa.String(60), nullable=True),
        sa.Column("transaction_category_level_2", sa.String(80), nullable=True),
        sa.Column("transaction_category_level_3", sa.String(60), nullable=True),

        sa.Column("project_corecon_id", sa.Integer(), nullable=True),
        sa.Column("project_number", sa.String(60), nullable=True),
        sa.Column("project_title", sa.String(500), nullable=True),
        sa.Column("project_pm_contact_name", sa.String(255), nullable=True),
        sa.Column("project_bid_contact_name", sa.String(255), nullable=True),
        sa.Column("project_sales_contact_name", sa.String(255), nullable=True),
        sa.Column("project_est_start_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_est_finish_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prime_contract_est_finish_date_incl_co_days_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("project_est_start_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("project_est_finish_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("prime_contract_est_finish_date_incl_co_days_org_local", sa.DateTime(timezone=False), nullable=True),

        sa.Column("prime_contract_corecon_id", sa.Integer(), nullable=True),
        sa.Column("prime_contract_number", sa.String(120), nullable=True),
        sa.Column("prime_contract_subject", sa.String(500), nullable=True),
        sa.Column("prime_contract_billing_type", sa.String(60), nullable=True),
        sa.Column("prime_contract_billing_type_value", sa.String(120), nullable=True),
        sa.Column("prime_contract_issue_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prime_contract_issue_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("prime_contract_approval_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prime_contract_approval_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("owner_company_name", sa.String(255), nullable=True),
        sa.Column("owner_contact", sa.String(255), nullable=True),
        sa.Column("prime_company_name", sa.String(255), nullable=True),
        sa.Column("prime_contact", sa.String(255), nullable=True),
        sa.Column("prime_contract_status", sa.String(60), nullable=True),
        sa.Column("prime_contract_est_start_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prime_contract_est_finish_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("prime_contract_est_start_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("prime_contract_est_finish_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("prime_contract_change_order_impact_days", sa.Integer(), nullable=True),

        sa.Column("co_corecon_id", sa.Integer(), nullable=True),
        sa.Column("co_number", sa.String(120), nullable=True),
        sa.Column("co_subject", sa.String(500), nullable=True),
        sa.Column("co_issue_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("co_issue_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("co_status_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("co_status_date_org_local", sa.DateTime(timezone=False), nullable=True),

        sa.Column("work_order_corecon_id", sa.Integer(), nullable=True),
        sa.Column("work_order_number", sa.String(120), nullable=True),
        sa.Column("work_order_subject", sa.String(500), nullable=True),
        sa.Column("work_order_issue_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("work_order_issue_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("work_order_status_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("work_order_status_date_org_local", sa.DateTime(timezone=False), nullable=True),

        sa.Column("job_cost_code_corecon_id", sa.Integer(), nullable=True),
        sa.Column("job_cost_code_order_number", sa.String(60), nullable=True),
        sa.Column("job_cost_code", sa.String(60), nullable=True),
        sa.Column("job_cost_code_description", sa.String(500), nullable=True),
        sa.Column("job_cost_code_quantity", sa.Numeric(15, 4), nullable=True),
        sa.Column("job_cost_code_unit", sa.String(20), nullable=True),
        sa.Column("job_cost_code_internal_division", sa.String(60), nullable=True),
        sa.Column("job_cost_code_internal_division_desc", sa.String(255), nullable=True),
        sa.Column("job_cost_code_internal_major", sa.String(60), nullable=True),
        sa.Column("job_cost_code_internal_major_desc", sa.String(255), nullable=True),
        sa.Column("job_cost_code_internal_minor", sa.String(60), nullable=True),
        sa.Column("job_cost_code_internal_minor_desc", sa.String(255), nullable=True),
        sa.Column("job_cost_code_internal_sub_minor", sa.String(60), nullable=True),
        sa.Column("job_cost_code_internal_sub_minor_desc", sa.String(255), nullable=True),
        sa.Column("owner_cost_code", sa.String(60), nullable=True),
        sa.Column("owner_cost_code_description", sa.String(500), nullable=True),

        sa.Column("transaction_corecon_id", sa.Integer(), nullable=False),
        sa.Column("transaction_number", sa.String(120), nullable=True),
        sa.Column("transaction_subject", sa.String(500), nullable=True),
        sa.Column("transaction_type", sa.String(120), nullable=True),
        sa.Column("transaction_status", sa.String(60), nullable=True),
        sa.Column("transaction_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("transaction_company_corecon_id", sa.Integer(), nullable=True),
        sa.Column("transaction_company_name", sa.String(255), nullable=True),
        sa.Column("transaction_company_code", sa.String(60), nullable=True),
        sa.Column("transaction_contact_corecon_id", sa.Integer(), nullable=True),
        sa.Column("transaction_contact", sa.String(255), nullable=True),
        sa.Column("transaction_export_status", sa.String(60), nullable=True),
        sa.Column("transaction_export_id", sa.String(60), nullable=True),
        sa.Column("transaction_export_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_export_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("transaction_payment_amount", sa.Numeric(15, 2), nullable=True),

        sa.Column("transaction_item_corecon_id", sa.Integer(), nullable=False),
        sa.Column("transaction_item_order_number", sa.String(60), nullable=True),
        sa.Column("transaction_item_description", sa.Text(), nullable=True),
        sa.Column("transaction_item_quantity", sa.Numeric(15, 4), nullable=True),
        sa.Column("transaction_item_unit", sa.String(20), nullable=True),
        sa.Column("transaction_item_unit_price", sa.Numeric(15, 4), nullable=True),
        sa.Column("transaction_item_unit_price_2", sa.Numeric(15, 4), nullable=True),
        sa.Column("transaction_item_gross_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_item_subtotal", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_item_subtotal_2", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_item_tax_id", sa.String(60), nullable=True),
        sa.Column("transaction_item_tax_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_item_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_item_invoiced_total", sa.Numeric(15, 2), nullable=True),
        sa.Column("transaction_invoiced_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_invoiced_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("transaction_item_resource_type", sa.String(20), nullable=True),
        sa.Column("transaction_item_billable_status", sa.String(60), nullable=True),
        sa.Column("transaction_start_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_start_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("transaction_finish_date_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_finish_date_org_local", sa.DateTime(timezone=False), nullable=True),
        sa.Column("transaction_project_multiplier", sa.Numeric(15, 6), nullable=True),
        sa.Column("transaction_org_multiplier", sa.Numeric(15, 6), nullable=True),
        sa.Column("transaction_item_created_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("transaction_item_modified_utc", sa.DateTime(timezone=True), nullable=True),

        sa.UniqueConstraint(
            "transaction_source",
            "transaction_corecon_id",
            "transaction_item_corecon_id",
            name="uq_corecon_transactions_source_txn_item",
        ),
    )

    op.create_index("ix_corecon_transactions_transaction_source", "corecon_transactions", ["transaction_source"])
    op.create_index("ix_corecon_transactions_project_corecon_id", "corecon_transactions", ["project_corecon_id"])
    op.create_index("ix_corecon_transactions_project_number", "corecon_transactions", ["project_number"])
    op.create_index("ix_corecon_transactions_prime_contract_corecon_id", "corecon_transactions", ["prime_contract_corecon_id"])
    op.create_index("ix_corecon_transactions_co_corecon_id", "corecon_transactions", ["co_corecon_id"])
    op.create_index("ix_corecon_transactions_job_cost_code_corecon_id", "corecon_transactions", ["job_cost_code_corecon_id"])
    op.create_index("ix_corecon_transactions_job_cost_code", "corecon_transactions", ["job_cost_code"])
    op.create_index("ix_corecon_transactions_transaction_corecon_id", "corecon_transactions", ["transaction_corecon_id"])
    op.create_index("ix_corecon_transactions_transaction_status", "corecon_transactions", ["transaction_status"])
    op.create_index("ix_corecon_transactions_transaction_date_utc", "corecon_transactions", ["transaction_date_utc"])
    op.create_index("ix_corecon_transactions_transaction_company_corecon_id", "corecon_transactions", ["transaction_company_corecon_id"])
    op.create_index("ix_corecon_transactions_transaction_item_corecon_id", "corecon_transactions", ["transaction_item_corecon_id"])
    op.create_index("ix_corecon_transactions_transaction_item_modified_utc", "corecon_transactions", ["transaction_item_modified_utc"])


def downgrade() -> None:
    op.drop_table("corecon_transactions")
