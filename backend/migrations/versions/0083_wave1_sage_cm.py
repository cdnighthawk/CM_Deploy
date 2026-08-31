"""Wave 1 Sage CM: cost codes, prime status, CPR/CO/SCO, directory, RFI/submittal.

Revision ID: 0083_wave1_sage
Revises: 0082_ingest_err
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0083_wave1_sage"
down_revision: Union[str, Sequence[str], None] = "0082_ingest_err"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rfi_cost_codes", sa.Column("order_number", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("rfi_cost_codes", sa.Column("quantity", sa.Numeric(15, 4), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("units", sa.String(length=40), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("owner_cost_code", sa.String(length=80), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("material_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("labor_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("equipment_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("subcontractor_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("other_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("revenue_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("labor_hour_budget", sa.Numeric(15, 2), nullable=True))
    op.add_column("rfi_cost_codes", sa.Column("equipment_hour_budget", sa.Numeric(15, 2), nullable=True))

    op.add_column("project_contracts", sa.Column("contract_type", sa.String(length=40), nullable=True))
    op.add_column("project_contracts", sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"))
    op.add_column("project_contracts", sa.Column("status_date", sa.Date(), nullable=True))

    op.add_column(
        "prime_contract_sov_lines",
        sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_prime_sov_cost_code",
        "prime_contract_sov_lines",
        "rfi_cost_codes",
        ["cost_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("prime_contract_sov_lines", sa.Column("quantity", sa.Numeric(15, 4), nullable=True))
    op.add_column("prime_contract_sov_lines", sa.Column("units", sa.String(length=40), nullable=True))

    op.add_column("pay_application_lines", sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_pay_app_line_cost_code",
        "pay_application_lines",
        "rfi_cost_codes",
        ["cost_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.add_column("pay_applications", sa.Column("status_date", sa.Date(), nullable=True))
    op.add_column(
        "pay_applications",
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column("commitments", sa.Column("subcontract_type", sa.String(length=40), nullable=True))

    op.add_column(
        "project_directory_companies",
        sa.Column("directory_role", sa.String(length=40), nullable=True),
    )

    op.add_column("rfis", sa.Column("originator_company_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("rfis", sa.Column("respondent_company_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_rfi_originator_co", "rfis", "companies", ["originator_company_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_rfi_respondent_co", "rfis", "companies", ["respondent_company_id"], ["id"], ondelete="SET NULL")

    op.add_column("submittal_line_items", sa.Column("status", sa.String(length=40), nullable=True))
    op.add_column("submittal_line_items", sa.Column("status_date", sa.Date(), nullable=True))
    op.add_column("submittal_line_items", sa.Column("quantity", sa.Numeric(15, 4), nullable=True))
    op.add_column("submittal_line_items", sa.Column("unit", sa.String(length=40), nullable=True))
    op.add_column("submittal_line_items", sa.Column("needed_on_site_date", sa.Date(), nullable=True))
    op.add_column("submittals", sa.Column("originator_company_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_submittal_originator_co",
        "submittals",
        "companies",
        ["originator_company_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "vendor_invoice_lines",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("invoice_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("unit_cost", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("resource", sa.String(length=40), nullable=True),
        sa.Column("billable", sa.String(length=20), nullable=True),
        sa.ForeignKeyConstraint(["invoice_id"], ["vendor_invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_vendor_invoice_lines_invoice_id", "vendor_invoice_lines", ["invoice_id"])

    _uuid = postgresql.UUID(as_uuid=True)
    _now = sa.text("now()")
    _uuid_default = sa.text("gen_random_uuid()")

    op.create_table(
        "change_proposal_requests",
        sa.Column("id", _uuid, server_default=_uuid_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("prime_contract_id", _uuid, nullable=True),
        sa.Column("number", sa.String(length=40), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("status_date", sa.Date(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("response_due_date", sa.Date(), nullable=True),
        sa.Column("impacted_company_id", _uuid, nullable=True),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", _uuid, nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prime_contract_id"], ["project_contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["impacted_company_id"], ["companies.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cpr_project_id", "change_proposal_requests", ["project_id"])

    op.create_table(
        "change_proposal_request_items",
        sa.Column("id", _uuid, server_default=_uuid_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("cpr_id", _uuid, nullable=False),
        sa.Column("cost_code_id", _uuid, nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("resource", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["cpr_id"], ["change_proposal_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_cpr_items_cpr_id", "change_proposal_request_items", ["cpr_id"])

    op.create_table(
        "owner_change_orders",
        sa.Column("id", _uuid, server_default=_uuid_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("prime_contract_id", _uuid, nullable=True),
        sa.Column("cpr_id", _uuid, nullable=True),
        sa.Column("number", sa.String(length=40), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("status_date", sa.Date(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", _uuid, nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["prime_contract_id"], ["project_contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cpr_id"], ["change_proposal_requests.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owner_co_project_id", "owner_change_orders", ["project_id"])

    op.create_table(
        "owner_change_order_items",
        sa.Column("id", _uuid, server_default=_uuid_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("change_order_id", _uuid, nullable=False),
        sa.Column("cost_code_id", _uuid, nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("resource", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["change_order_id"], ["owner_change_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_owner_co_items_co_id", "owner_change_order_items", ["change_order_id"])

    op.create_table(
        "subcontract_change_orders",
        sa.Column("id", _uuid, server_default=_uuid_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("project_id", _uuid, nullable=False),
        sa.Column("commitment_id", _uuid, nullable=False),
        sa.Column("number", sa.String(length=40), nullable=True),
        sa.Column("subject", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
        sa.Column("status_date", sa.Date(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", _uuid, nullable=True),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sco_project_id", "subcontract_change_orders", ["project_id"])
    op.create_index("ix_sco_commitment_id", "subcontract_change_orders", ["commitment_id"])

    op.create_table(
        "subcontract_change_order_items",
        sa.Column("id", _uuid, server_default=_uuid_default, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_now, nullable=False),
        sa.Column("sco_id", _uuid, nullable=False),
        sa.Column("cost_code_id", _uuid, nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("description", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("quantity", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=40), nullable=True),
        sa.Column("unit_price", sa.Numeric(15, 4), nullable=False, server_default="0"),
        sa.Column("line_total", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("resource", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(["sco_id"], ["subcontract_change_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sco_items_sco_id", "subcontract_change_order_items", ["sco_id"])


def downgrade() -> None:
    op.drop_table("subcontract_change_order_items")
    op.drop_table("subcontract_change_orders")
    op.drop_table("owner_change_order_items")
    op.drop_table("owner_change_orders")
    op.drop_table("change_proposal_request_items")
    op.drop_table("change_proposal_requests")
    op.drop_table("vendor_invoice_lines")
    op.drop_constraint("fk_submittal_originator_co", "submittals", type_="foreignkey")
    op.drop_column("submittals", "originator_company_id")
    op.drop_column("submittal_line_items", "needed_on_site_date")
    op.drop_column("submittal_line_items", "unit")
    op.drop_column("submittal_line_items", "quantity")
    op.drop_column("submittal_line_items", "status_date")
    op.drop_column("submittal_line_items", "status")
    op.drop_constraint("fk_rfi_respondent_co", "rfis", type_="foreignkey")
    op.drop_constraint("fk_rfi_originator_co", "rfis", type_="foreignkey")
    op.drop_column("rfis", "respondent_company_id")
    op.drop_column("rfis", "originator_company_id")
    op.drop_column("project_directory_companies", "directory_role")
    op.drop_column("commitments", "subcontract_type")
    op.drop_column("pay_applications", "approved")
    op.drop_column("pay_applications", "status_date")
    op.drop_constraint("fk_pay_app_line_cost_code", "pay_application_lines", type_="foreignkey")
    op.drop_column("pay_application_lines", "cost_code_id")
    op.drop_constraint("fk_prime_sov_cost_code", "prime_contract_sov_lines", type_="foreignkey")
    op.drop_column("prime_contract_sov_lines", "units")
    op.drop_column("prime_contract_sov_lines", "quantity")
    op.drop_column("prime_contract_sov_lines", "cost_code_id")
    op.drop_column("project_contracts", "status_date")
    op.drop_column("project_contracts", "status")
    op.drop_column("project_contracts", "contract_type")
    for col in (
        "equipment_hour_budget",
        "labor_hour_budget",
        "revenue_budget",
        "other_budget",
        "subcontractor_budget",
        "equipment_budget",
        "labor_budget",
        "material_budget",
        "owner_cost_code",
        "units",
        "quantity",
        "order_number",
    ):
        op.drop_column("rfi_cost_codes", col)
