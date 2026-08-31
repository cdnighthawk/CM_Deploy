"""Wave 2 Sage CM: field extras, PO COs, subinvoices, meetings, insurance.

Revision ID: 0084_wave2_sage
Revises: 0083_wave1_sage
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0084_wave2_sage"
down_revision: Union[str, Sequence[str], None] = "0083_wave1_sage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk():
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        nullable=False,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps():
    return (
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def upgrade() -> None:
    op.add_column("field_photos", sa.Column("album", sa.String(length=120), nullable=True))
    op.add_column(
        "hrms_timesheet_entries",
        sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "hrms_timesheet_entries",
        sa.Column("time_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_hrms_timesheet_entries_cost_code",
        "hrms_timesheet_entries",
        "rfi_cost_codes",
        ["cost_code_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_hrms_timesheet_entries_time_entry",
        "hrms_timesheet_entries",
        "time_entries",
        ["time_entry_id"],
        ["id"],
        ondelete="SET NULL",
    )

    ts = _timestamps()
    op.create_table(
        "transmittals",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("transmittal_type", sa.String(80), nullable=True),
        sa.Column("from_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("to_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *ts,
    )
    op.create_index("ix_transmittals_project_id", "transmittals", ["project_id"])

    op.create_table(
        "punchlist_items",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("title", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("responsible_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("inspection_date", sa.Date(), nullable=True),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *ts,
    )
    op.create_index("ix_punchlist_items_project_id", "punchlist_items", ["project_id"])

    op.create_table(
        "work_orders",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("work_order_type", sa.String(80), nullable=True),
        sa.Column("issued_to_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        *ts,
    )
    op.create_index("ix_work_orders_project_id", "work_orders", ["project_id"])

    op.create_table(
        "anticipated_costs",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("rfi_cost_codes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("accounted_for", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text(), nullable=True),
        *ts,
    )
    op.create_index("ix_anticipated_costs_project_id", "anticipated_costs", ["project_id"])

    op.create_table(
        "purchase_order_change_orders",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commitment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("status_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        *ts,
    )
    op.create_index("ix_purchase_order_change_orders_project_id", "purchase_order_change_orders", ["project_id"])
    op.create_index("ix_purchase_order_change_orders_commitment_id", "purchase_order_change_orders", ["commitment_id"])

    op.create_table(
        "sub_invoices",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commitment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("commitments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("approved", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status_date", sa.Date(), nullable=True),
        sa.Column("invoice_date", sa.Date(), nullable=True),
        sa.Column("amount", sa.Numeric(15, 2), nullable=True),
        sa.Column("retainage", sa.Numeric(15, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("lines", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *ts,
    )
    op.create_index("ix_sub_invoices_project_id", "sub_invoices", ["project_id"])

    op.create_table(
        "meetings",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="scheduled"),
        sa.Column("meeting_date", sa.Date(), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attendees", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *ts,
    )
    op.create_index("ix_meetings_project_id", "meetings", ["project_id"])

    op.create_table(
        "safety_incidents",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("incident_date", sa.Date(), nullable=True),
        sa.Column("severity", sa.String(40), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("injuries", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *ts,
    )
    op.create_index("ix_safety_incidents_project_id", "safety_incidents", ["project_id"])

    op.create_table(
        "company_insurance_policies",
        _uuid_pk(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("policy_type", sa.String(80), nullable=True),
        sa.Column("carrier", sa.String(255), nullable=True),
        sa.Column("policy_number", sa.String(80), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("coverage_limit", sa.Numeric(15, 2), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *ts,
    )
    op.create_index("ix_company_insurance_policies_company_id", "company_insurance_policies", ["company_id"])

    op.create_table(
        "company_licenses",
        _uuid_pk(),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("license_type", sa.String(80), nullable=True),
        sa.Column("license_number", sa.String(80), nullable=True),
        sa.Column("jurisdiction", sa.String(120), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *ts,
    )
    op.create_index("ix_company_licenses_company_id", "company_licenses", ["company_id"])

    op.create_table(
        "issue_companies",
        _uuid_pk(),
        sa.Column("issue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tracker_issues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(80), nullable=True),
        *ts,
        sa.UniqueConstraint("issue_id", "company_id", name="uq_issue_companies_issue_company"),
    )
    op.create_index("ix_issue_companies_issue_id", "issue_companies", ["issue_id"])
    op.create_index("ix_issue_companies_company_id", "issue_companies", ["company_id"])

    op.create_table(
        "workflow_amount_rules",
        _uuid_pk(),
        sa.Column("transaction_type", sa.String(80), nullable=False),
        sa.Column("min_amount", sa.Numeric(15, 2), nullable=False, server_default="0"),
        sa.Column("approver_role", sa.String(80), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("notes", sa.Text(), nullable=True),
        *ts,
    )
    op.create_index("ix_workflow_amount_rules_transaction_type", "workflow_amount_rules", ["transaction_type"])

    op.create_table(
        "qc_checklists",
        _uuid_pk(),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("review_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("items", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        *ts,
    )
    op.create_index("ix_qc_checklists_project_id", "qc_checklists", ["project_id"])


def downgrade() -> None:
    for table in (
        "qc_checklists",
        "workflow_amount_rules",
        "issue_companies",
        "company_licenses",
        "company_insurance_policies",
        "safety_incidents",
        "meetings",
        "sub_invoices",
        "purchase_order_change_orders",
        "anticipated_costs",
        "work_orders",
        "punchlist_items",
        "transmittals",
    ):
        op.drop_table(table)
    op.drop_constraint("fk_hrms_timesheet_entries_time_entry", "hrms_timesheet_entries", type_="foreignkey")
    op.drop_constraint("fk_hrms_timesheet_entries_cost_code", "hrms_timesheet_entries", type_="foreignkey")
    op.drop_column("hrms_timesheet_entries", "time_entry_id")
    op.drop_column("hrms_timesheet_entries", "cost_code_id")
    op.drop_column("field_photos", "album")
