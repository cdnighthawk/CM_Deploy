"""HRMS foundation: org structure, employee profiles, leave, timesheets, shifts, goals, reviews, expenses, GDPR, audit.

Revision ID: 0030_hrms_foundation
Revises: 0029_project_schedule_items
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0030_hrms_foundation"
down_revision: Union[str, Sequence[str], None] = "0029_project_schedule_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid_pk():
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "hrms_org_units",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("parent_id", _uuid_pk(), nullable=True),
        sa.Column("company_id", _uuid_pk(), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["hrms_org_units.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_org_units_parent_id", "hrms_org_units", ["parent_id"])
    op.create_index("ix_hrms_org_units_company_id", "hrms_org_units", ["company_id"])

    op.create_table(
        "hrms_module_settings",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_hrms_module_settings_key", "hrms_module_settings", ["key"], unique=True)

    op.create_table(
        "hrms_leave_types",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_attachment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("accrual_hours_per_month", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_carryover_hours", sa.Numeric(10, 2), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("uq_hrms_leave_types_code", "hrms_leave_types", ["code"], unique=True)

    op.create_table(
        "hrms_employee_profiles",
        sa.Column("user_id", _uuid_pk(), primary_key=True),
        sa.Column("org_unit_id", _uuid_pk(), nullable=True),
        sa.Column("manager_user_id", _uuid_pk(), nullable=True),
        sa.Column("job_title", sa.String(200), nullable=True),
        sa.Column("hire_date", sa.Date(), nullable=True),
        sa.Column("termination_date", sa.Date(), nullable=True),
        sa.Column("employment_status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("custom_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pii_storage_hint", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["org_unit_id"], ["hrms_org_units.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["manager_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_employee_profiles_org_unit_id", "hrms_employee_profiles", ["org_unit_id"])
    op.create_index("ix_hrms_employee_profiles_manager_user_id", "hrms_employee_profiles", ["manager_user_id"])

    op.create_table(
        "hrms_leave_balances",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("leave_type_id", _uuid_pk(), nullable=False),
        sa.Column("accrual_year", sa.Integer(), nullable=False),
        sa.Column("balance_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("accrued_ytd_hours", sa.Numeric(10, 2), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["hrms_leave_types.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "leave_type_id", "accrual_year", name="uq_hrms_leave_balance_user_type_year"),
    )
    op.create_index("ix_hrms_leave_balances_user_id", "hrms_leave_balances", ["user_id"])

    op.create_table(
        "hrms_leave_requests",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("leave_type_id", _uuid_pk(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hours_requested", sa.Numeric(10, 2), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("approver_user_id", _uuid_pk(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["leave_type_id"], ["hrms_leave_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_leave_requests_user_id", "hrms_leave_requests", ["user_id"])
    op.create_index("ix_hrms_leave_requests_status", "hrms_leave_requests", ["status"])

    op.create_table(
        "hrms_timesheet_periods",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("approver_user_id", _uuid_pk(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("user_id", "period_start", name="uq_hrms_timesheet_period_user_start"),
    )
    op.create_index("ix_hrms_timesheet_periods_user_id", "hrms_timesheet_periods", ["user_id"])

    op.create_table(
        "hrms_timesheet_entries",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("period_id", _uuid_pk(), nullable=False),
        sa.Column("work_date", sa.Date(), nullable=False),
        sa.Column("hours_worked", sa.Numeric(8, 2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("filled_from_leave", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("project_id", _uuid_pk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["period_id"], ["hrms_timesheet_periods.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_timesheet_entries_period_id", "hrms_timesheet_entries", ["period_id"])

    op.create_table(
        "hrms_shifts",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("org_unit_id", _uuid_pk(), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_unit_id"], ["hrms_org_units.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_shifts_org_unit_id", "hrms_shifts", ["org_unit_id"])
    op.create_index("ix_hrms_shifts_start_at", "hrms_shifts", ["start_at"])

    op.create_table(
        "hrms_shift_assignments",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("shift_id", _uuid_pk(), nullable=False),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("assignment_status", sa.String(32), nullable=False, server_default="assigned"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["shift_id"], ["hrms_shifts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("shift_id", "user_id", name="uq_hrms_shift_assignment_shift_user"),
    )
    op.create_index("ix_hrms_shift_assignments_user_id", "hrms_shift_assignments", ["user_id"])

    op.create_table(
        "hrms_shift_swaps",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("from_assignment_id", _uuid_pk(), nullable=False),
        sa.Column("to_shift_id", _uuid_pk(), nullable=True),
        sa.Column("target_user_id", _uuid_pk(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("approver_user_id", _uuid_pk(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["from_assignment_id"], ["hrms_shift_assignments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_shift_id"], ["hrms_shifts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_shift_swaps_status", "hrms_shift_swaps", ["status"])

    op.create_table(
        "hrms_goals",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("owner_user_id", _uuid_pk(), nullable=False),
        sa.Column("scope", sa.String(16), nullable=False, server_default="individual"),
        sa.Column("team_key", sa.String(80), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("target_metrics", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hrms_goals_owner_user_id", "hrms_goals", ["owner_user_id"])

    op.create_table(
        "hrms_goal_updates",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("goal_id", _uuid_pk(), nullable=False),
        sa.Column("author_user_id", _uuid_pk(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("progress_percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["hrms_goals.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hrms_goal_updates_goal_id", "hrms_goal_updates", ["goal_id"])

    op.create_table(
        "hrms_review_cycles",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("opens_at", sa.Date(), nullable=True),
        sa.Column("closes_at", sa.Date(), nullable=True),
        sa.Column("template_ref", sa.String(120), nullable=True),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "hrms_review_instances",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("cycle_id", _uuid_pk(), nullable=False),
        sa.Column("subject_user_id", _uuid_pk(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["cycle_id"], ["hrms_review_cycles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["subject_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hrms_review_instances_subject", "hrms_review_instances", ["subject_user_id"])

    op.create_table(
        "hrms_review_scores",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("instance_id", _uuid_pk(), nullable=False),
        sa.Column("reviewer_user_id", _uuid_pk(), nullable=False),
        sa.Column("scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["instance_id"], ["hrms_review_instances.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewer_user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hrms_review_scores_instance_id", "hrms_review_scores", ["instance_id"])

    op.create_table(
        "hrms_expense_reports",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approver_user_id", _uuid_pk(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["approver_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_expense_reports_user_id", "hrms_expense_reports", ["user_id"])

    op.create_table(
        "hrms_expense_lines",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("report_id", _uuid_pk(), nullable=False),
        sa.Column("spent_at", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("receipt_document_id", _uuid_pk(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["report_id"], ["hrms_expense_reports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["receipt_document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_expense_lines_report_id", "hrms_expense_lines", ["report_id"])

    op.create_table(
        "hrms_notifications",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hrms_notifications_user_id", "hrms_notifications", ["user_id"])
    op.create_index("ix_hrms_notifications_read_at", "hrms_notifications", ["read_at"])

    op.create_table(
        "hrms_gdpr_consents",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", _uuid_pk(), nullable=False),
        sa.Column("purpose", sa.String(120), nullable=False),
        sa.Column("consent_version", sa.String(40), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_hrms_gdpr_consents_user_id", "hrms_gdpr_consents", ["user_id"])

    op.create_table(
        "hrms_audit_logs",
        sa.Column("id", _uuid_pk(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("actor_user_id", _uuid_pk(), nullable=True),
        sa.Column("action", sa.String(80), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=False),
        sa.Column("entity_id", _uuid_pk(), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hrms_audit_logs_entity", "hrms_audit_logs", ["entity_type", "entity_id"])
    op.create_index("ix_hrms_audit_logs_created_at", "hrms_audit_logs", ["created_at"])

    # Seed leave types + default module flags (idempotent)
    op.execute(
        sa.text(
            """
            INSERT INTO hrms_leave_types (id, code, name, paid, requires_attachment, sort_order, is_active, created_at, updated_at)
            SELECT gen_random_uuid(), v.code, v.name, v.paid, v.requires_attachment, v.ord, true, now(), now()
            FROM (VALUES
                ('vacation', 'Vacation', true, false, 10),
                ('sick', 'Sick leave', true, false, 20),
                ('personal', 'Personal', true, false, 30),
                ('unpaid', 'Unpaid leave', false, false, 40)
            ) AS v(code, name, paid, requires_attachment, ord)
            WHERE NOT EXISTS (SELECT 1 FROM hrms_leave_types t WHERE t.code = v.code);
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO hrms_module_settings (id, key, value, created_at, updated_at)
            SELECT gen_random_uuid(), 'feature_flags',
                   '{"employees": true, "org_chart": true, "self_service": true, "onboarding": true, "directory": true,
                     "leave": true, "timesheets": true, "shifts": true, "performance": true, "expenses": true,
                     "dashboards": true, "recruitment": false}'::jsonb,
                   now(), now()
            WHERE NOT EXISTS (SELECT 1 FROM hrms_module_settings s WHERE s.key = 'feature_flags');
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_hrms_audit_logs_created_at", table_name="hrms_audit_logs")
    op.drop_index("ix_hrms_audit_logs_entity", table_name="hrms_audit_logs")
    op.drop_table("hrms_audit_logs")

    op.drop_index("ix_hrms_gdpr_consents_user_id", table_name="hrms_gdpr_consents")
    op.drop_table("hrms_gdpr_consents")

    op.drop_index("ix_hrms_notifications_read_at", table_name="hrms_notifications")
    op.drop_index("ix_hrms_notifications_user_id", table_name="hrms_notifications")
    op.drop_table("hrms_notifications")

    op.drop_index("ix_hrms_expense_lines_report_id", table_name="hrms_expense_lines")
    op.drop_table("hrms_expense_lines")

    op.drop_index("ix_hrms_expense_reports_user_id", table_name="hrms_expense_reports")
    op.drop_table("hrms_expense_reports")

    op.drop_index("ix_hrms_review_scores_instance_id", table_name="hrms_review_scores")
    op.drop_table("hrms_review_scores")

    op.drop_index("ix_hrms_review_instances_subject", table_name="hrms_review_instances")
    op.drop_table("hrms_review_instances")

    op.drop_table("hrms_review_cycles")

    op.drop_index("ix_hrms_goal_updates_goal_id", table_name="hrms_goal_updates")
    op.drop_table("hrms_goal_updates")

    op.drop_index("ix_hrms_goals_owner_user_id", table_name="hrms_goals")
    op.drop_table("hrms_goals")

    op.drop_index("ix_hrms_shift_swaps_status", table_name="hrms_shift_swaps")
    op.drop_table("hrms_shift_swaps")

    op.drop_index("ix_hrms_shift_assignments_user_id", table_name="hrms_shift_assignments")
    op.drop_table("hrms_shift_assignments")

    op.drop_index("ix_hrms_shifts_start_at", table_name="hrms_shifts")
    op.drop_index("ix_hrms_shifts_org_unit_id", table_name="hrms_shifts")
    op.drop_table("hrms_shifts")

    op.drop_index("ix_hrms_timesheet_entries_period_id", table_name="hrms_timesheet_entries")
    op.drop_table("hrms_timesheet_entries")

    op.drop_index("ix_hrms_timesheet_periods_user_id", table_name="hrms_timesheet_periods")
    op.drop_table("hrms_timesheet_periods")

    op.drop_index("ix_hrms_leave_requests_status", table_name="hrms_leave_requests")
    op.drop_index("ix_hrms_leave_requests_user_id", table_name="hrms_leave_requests")
    op.drop_table("hrms_leave_requests")

    op.drop_index("ix_hrms_leave_balances_user_id", table_name="hrms_leave_balances")
    op.drop_table("hrms_leave_balances")

    op.drop_index("ix_hrms_employee_profiles_manager_user_id", table_name="hrms_employee_profiles")
    op.drop_index("ix_hrms_employee_profiles_org_unit_id", table_name="hrms_employee_profiles")
    op.drop_table("hrms_employee_profiles")

    op.drop_index("uq_hrms_leave_types_code", table_name="hrms_leave_types")
    op.drop_table("hrms_leave_types")

    op.drop_index("uq_hrms_module_settings_key", table_name="hrms_module_settings")
    op.drop_table("hrms_module_settings")

    op.drop_index("ix_hrms_org_units_company_id", table_name="hrms_org_units")
    op.drop_index("ix_hrms_org_units_parent_id", table_name="hrms_org_units")
    op.drop_table("hrms_org_units")
