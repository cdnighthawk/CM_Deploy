"""Expand RFIs to full Procore parity.

This migration:

- Replaces the bare ``rfis`` table with the full Procore field set
  (enums for status / impact choice, prefix + revision_index, soft-delete,
  date_initiated_at / closed_at, ball-in-court, official response, all
  people FKs, and lookup FKs).
- Adds project-scoped lookup tables: ``rfi_locations``, ``rfi_spec_sections``,
  ``rfi_cost_codes``, ``rfi_project_stages``, ``rfi_sub_jobs``.
- Adds join tables: ``rfi_assignees``, ``rfi_distribution``.
- Adds workflow tables: ``rfi_replies``, ``rfi_audit``.
- Adds Procore power-feature tables: ``rfi_revisions``,
  ``rfi_custom_field_defs``, ``rfi_custom_field_values``,
  ``rfi_configurable_fields``, ``rfi_saved_views``, ``rfi_column_prefs``.
- Adds notification log: ``rfi_notification_log``.

The existing ``rfis`` table is empty in dev (no inserts in seed data) so we
drop + recreate rather than performing an in-place ALTER for every column.

Revision ID: 0011_rfi_procore_expand
Revises: 0010_takeoff_line_items
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_rfi_procore_expand"
down_revision: Union[str, Sequence[str], None] = "0010_takeoff_line_items"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_enums() -> None:
    op.execute(
        "CREATE TYPE rfi_status AS ENUM ('draft','open','closed','closed_draft')"
    )
    op.execute(
        "CREATE TYPE rfi_impact_choice AS ENUM ('yes','yes_unknown','no','tbd','na')"
    )
    op.execute(
        "CREATE TYPE rfi_audit_action AS ENUM ("
        "'create','edit','status_change','ball_in_court',"
        "'assignee_add','assignee_remove','distribution_add','distribution_remove',"
        "'reply_add','reply_delete','official_response_set',"
        "'close','reopen','forward','email_sent','revision',"
        "'attachment_add','attachment_remove','restore','delete')"
    )
    op.execute("CREATE TYPE rfi_view_scope AS ENUM ('user','project','company')")
    op.execute(
        "CREATE TYPE rfi_custom_field_type AS ENUM ('number','date','checkbox','plain_text')"
    )
    op.execute(
        "CREATE TYPE rfi_field_requirement AS ENUM ('required','optional','hidden')"
    )


def _drop_enums() -> None:
    for name in (
        "rfi_field_requirement",
        "rfi_custom_field_type",
        "rfi_view_scope",
        "rfi_audit_action",
        "rfi_impact_choice",
        "rfi_status",
    ):
        op.execute(f"DROP TYPE IF EXISTS {name}")


# ---------------------------------------------------------------------------
# Upgrade
# ---------------------------------------------------------------------------


def upgrade() -> None:
    op.drop_index("ix_rfis_status", table_name="rfis", if_exists=True)
    op.drop_index("ix_rfis_project_id", table_name="rfis", if_exists=True)
    op.drop_table("rfis")

    _create_enums()

    # Lookups -----------------------------------------------------------------
    op.create_table(
        "rfi_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("path", sa.String(500), nullable=False),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["rfi_locations.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "path", name="uq_rfi_locations_project_path"),
    )
    op.create_index("ix_rfi_locations_project_id", "rfi_locations", ["project_id"])

    op.create_table(
        "rfi_spec_sections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "code", name="uq_rfi_spec_sections_project_code"),
    )
    op.create_index("ix_rfi_spec_sections_project_id", "rfi_spec_sections", ["project_id"])

    op.create_table(
        "rfi_cost_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "code", name="uq_rfi_cost_codes_project_code"),
    )
    op.create_index("ix_rfi_cost_codes_project_id", "rfi_cost_codes", ["project_id"])

    op.create_table(
        "rfi_project_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "code", name="uq_rfi_project_stages_project_code"),
    )
    op.create_index("ix_rfi_project_stages_project_id", "rfi_project_stages", ["project_id"])

    op.create_table(
        "rfi_sub_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("name", sa.String(300), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "code", name="uq_rfi_sub_jobs_project_code"),
    )
    op.create_index("ix_rfi_sub_jobs_project_id", "rfi_sub_jobs", ["project_id"])

    # RFI header --------------------------------------------------------------
    op.create_table(
        "rfis",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("prefix", sa.String(20), nullable=True),
        sa.Column("revision_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("general_information", sa.Text(), nullable=True),
        sa.Column("reference_text", sa.String(500), nullable=True),
        sa.Column(
            "status",
            postgresql.ENUM(name="rfi_status", create_type=False),
            nullable=False,
            server_default="draft",
        ),
        sa.Column("is_private", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("date_initiated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "cost_impact_choice",
            postgresql.ENUM(name="rfi_impact_choice", create_type=False),
            nullable=True,
        ),
        sa.Column("cost_impact", sa.Numeric(15, 2), nullable=True),
        sa.Column(
            "schedule_impact_choice",
            postgresql.ENUM(name="rfi_impact_choice", create_type=False),
            nullable=True,
        ),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("ball_in_court", sa.String(200), nullable=True),
        sa.Column("official_response_reply_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("official_response", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rfi_manager_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("received_from_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("responsible_contractor_company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("location_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("spec_section_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_stage_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("sub_job_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("drawing_number_text", sa.String(120), nullable=True),
        sa.Column("revision_of_rfi_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("extra", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rfi_manager_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["received_from_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["responsible_contractor_company_id"], ["companies.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["location_id"], ["rfi_locations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["spec_section_id"], ["rfi_spec_sections.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_stage_id"], ["rfi_project_stages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["sub_job_id"], ["rfi_sub_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["revision_of_rfi_id"], ["rfis.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("project_id", "number", "revision_index", name="uq_rfis_project_number_rev"),
    )
    op.create_index("ix_rfis_project_id", "rfis", ["project_id"])
    op.create_index("ix_rfis_status", "rfis", ["status"])
    op.create_index("ix_rfis_rfi_manager_user_id", "rfis", ["rfi_manager_user_id"])
    op.create_index("ix_rfis_is_deleted", "rfis", ["is_deleted"])

    # Join tables -------------------------------------------------------------
    op.create_table(
        "rfi_assignees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("ball_in_court", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("rfi_id", "user_id", name="uq_rfi_assignees_rfi_user"),
    )
    op.create_index("ix_rfi_assignees_rfi_id", "rfi_assignees", ["rfi_id"])
    op.create_index("ix_rfi_assignees_user_id", "rfi_assignees", ["user_id"])

    op.create_table(
        "rfi_distribution",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("rfi_id", "user_id", name="uq_rfi_distribution_rfi_user"),
    )
    op.create_index("ix_rfi_distribution_rfi_id", "rfi_distribution", ["rfi_id"])
    op.create_index("ix_rfi_distribution_user_id", "rfi_distribution", ["user_id"])

    # Replies + audit ---------------------------------------------------------
    op.create_table(
        "rfi_replies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("is_official", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rfi_replies_rfi_id", "rfi_replies", ["rfi_id"])

    op.create_foreign_key(
        "fk_rfis_official_response_reply_id",
        "rfis",
        "rfi_replies",
        ["official_response_reply_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "rfi_audit",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "action",
            postgresql.ENUM(name="rfi_audit_action", create_type=False),
            nullable=False,
        ),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rfi_audit_rfi_id", "rfi_audit", ["rfi_id"])
    op.create_index("ix_rfi_audit_action", "rfi_audit", ["action"])

    # Revisions / custom / configurable --------------------------------------
    op.create_table(
        "rfi_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("revision_index", sa.Integer(), nullable=False),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rfi_revisions_rfi_id", "rfi_revisions", ["rfi_id"])

    op.create_table(
        "rfi_custom_field_defs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column(
            "field_type",
            postgresql.ENUM(name="rfi_custom_field_type", create_type=False),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rfi_custom_field_defs_company_id", "rfi_custom_field_defs", ["company_id"])

    op.create_table(
        "rfi_custom_field_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("field_def_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("value_number", sa.Numeric(20, 6), nullable=True),
        sa.Column("value_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("value_bool", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["field_def_id"], ["rfi_custom_field_defs.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("rfi_id", "field_def_id", name="uq_rfi_custom_field_values_rfi_def"),
    )
    op.create_index("ix_rfi_custom_field_values_rfi_id", "rfi_custom_field_values", ["rfi_id"])
    op.create_index(
        "ix_rfi_custom_field_values_field_def_id", "rfi_custom_field_values", ["field_def_id"]
    )

    op.create_table(
        "rfi_configurable_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("field_key", sa.String(80), nullable=False),
        sa.Column(
            "requirement",
            postgresql.ENUM(name="rfi_field_requirement", create_type=False),
            nullable=False,
            server_default="optional",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "field_key", name="uq_rfi_configurable_fields_project_field"),
    )
    op.create_index("ix_rfi_configurable_fields_project_id", "rfi_configurable_fields", ["project_id"])

    # Saved views + column prefs ---------------------------------------------
    op.create_table(
        "rfi_saved_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column(
            "scope",
            postgresql.ENUM(name="rfi_view_scope", create_type=False),
            nullable=False,
            server_default="user",
        ),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("sort", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_rfi_saved_views_owner_user_id", "rfi_saved_views", ["owner_user_id"])
    op.create_index("ix_rfi_saved_views_project_id", "rfi_saved_views", ["project_id"])
    op.create_index("ix_rfi_saved_views_company_id", "rfi_saved_views", ["company_id"])

    op.create_table(
        "rfi_column_prefs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_key", sa.String(120), nullable=False),
        sa.Column("columns", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("row_height", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id", "scope_key", name="uq_rfi_column_prefs_user_scope"),
    )
    op.create_index("ix_rfi_column_prefs_user_id", "rfi_column_prefs", ["user_id"])

    # Notification log -------------------------------------------------------
    op.create_table(
        "rfi_notification_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rfi_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event", sa.String(80), nullable=False),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("recipient_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("body_preview", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["rfi_id"], ["rfis.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipient_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_rfi_notification_log_rfi_id", "rfi_notification_log", ["rfi_id"])
    op.create_index("ix_rfi_notification_log_event", "rfi_notification_log", ["event"])


# ---------------------------------------------------------------------------
# Downgrade
# ---------------------------------------------------------------------------


def downgrade() -> None:
    for ix, tbl in (
        ("ix_rfi_notification_log_event", "rfi_notification_log"),
        ("ix_rfi_notification_log_rfi_id", "rfi_notification_log"),
    ):
        op.drop_index(ix, table_name=tbl)
    op.drop_table("rfi_notification_log")

    op.drop_index("ix_rfi_column_prefs_user_id", table_name="rfi_column_prefs")
    op.drop_table("rfi_column_prefs")

    for ix in (
        "ix_rfi_saved_views_company_id",
        "ix_rfi_saved_views_project_id",
        "ix_rfi_saved_views_owner_user_id",
    ):
        op.drop_index(ix, table_name="rfi_saved_views")
    op.drop_table("rfi_saved_views")

    op.drop_index("ix_rfi_configurable_fields_project_id", table_name="rfi_configurable_fields")
    op.drop_table("rfi_configurable_fields")

    op.drop_index("ix_rfi_custom_field_values_field_def_id", table_name="rfi_custom_field_values")
    op.drop_index("ix_rfi_custom_field_values_rfi_id", table_name="rfi_custom_field_values")
    op.drop_table("rfi_custom_field_values")

    op.drop_index("ix_rfi_custom_field_defs_company_id", table_name="rfi_custom_field_defs")
    op.drop_table("rfi_custom_field_defs")

    op.drop_index("ix_rfi_revisions_rfi_id", table_name="rfi_revisions")
    op.drop_table("rfi_revisions")

    op.drop_index("ix_rfi_audit_action", table_name="rfi_audit")
    op.drop_index("ix_rfi_audit_rfi_id", table_name="rfi_audit")
    op.drop_table("rfi_audit")

    op.drop_constraint("fk_rfis_official_response_reply_id", "rfis", type_="foreignkey")
    op.drop_index("ix_rfi_replies_rfi_id", table_name="rfi_replies")
    op.drop_table("rfi_replies")

    for ix in ("ix_rfi_distribution_user_id", "ix_rfi_distribution_rfi_id"):
        op.drop_index(ix, table_name="rfi_distribution")
    op.drop_table("rfi_distribution")

    for ix in ("ix_rfi_assignees_user_id", "ix_rfi_assignees_rfi_id"):
        op.drop_index(ix, table_name="rfi_assignees")
    op.drop_table("rfi_assignees")

    for ix in ("ix_rfis_is_deleted", "ix_rfis_rfi_manager_user_id", "ix_rfis_status", "ix_rfis_project_id"):
        op.drop_index(ix, table_name="rfis")
    op.drop_table("rfis")

    for tbl in (
        ("rfi_sub_jobs", "ix_rfi_sub_jobs_project_id"),
        ("rfi_project_stages", "ix_rfi_project_stages_project_id"),
        ("rfi_cost_codes", "ix_rfi_cost_codes_project_id"),
        ("rfi_spec_sections", "ix_rfi_spec_sections_project_id"),
        ("rfi_locations", "ix_rfi_locations_project_id"),
    ):
        op.drop_index(tbl[1], table_name=tbl[0])
        op.drop_table(tbl[0])

    _drop_enums()

    # Recreate the bare ``rfis`` table to match 0009_project_rfis_submittals
    op.create_table(
        "rfis",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("ball_in_court", sa.String(200), nullable=True),
        sa.Column("question", sa.Text(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cost_impact", sa.Numeric(15, 2), nullable=True),
        sa.Column("schedule_impact_days", sa.Integer(), nullable=True),
        sa.Column("official_response", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("project_id", "number", name="uq_rfis_project_number"),
    )
    op.create_index("ix_rfis_project_id", "rfis", ["project_id"])
    op.create_index("ix_rfis_status", "rfis", ["status"])
