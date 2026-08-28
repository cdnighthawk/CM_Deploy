"""Submittal QC gate, amendable workflow engine, PO hold columns.

Revision ID: 0063_submittal_qc
Revises: 0062_po_shipments_receipts
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0063_submittal_qc"
down_revision: Union[str, Sequence[str], None] = "0062_po_shipments_receipts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("require_ae_before_release", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "projects",
        sa.Column("allow_po_without_submittal", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.create_table(
        "workflow_definitions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("process_key", sa.String(80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_definitions_process_key", "workflow_definitions", ["process_key"])
    op.create_index("ix_workflow_definitions_project_id", "workflow_definitions", ["project_id"])
    op.create_unique_constraint(
        "uq_workflow_definitions_key_version_project",
        "workflow_definitions",
        ["process_key", "version", "project_id"],
    )

    op.create_table(
        "workflow_definition_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_key", sa.String(80), nullable=True),
        sa.Column("required_actions", postgresql.JSONB(), nullable=True),
        sa.Column("on_approve_status", sa.String(40), nullable=True),
        sa.Column("entry_condition", sa.String(200), nullable=True),
        sa.Column("skippable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_definition_steps_definition_id", "workflow_definition_steps", ["definition_id"])

    op.create_table(
        "workflow_queues",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("process_key", sa.String(80), nullable=False),
        sa.Column("queue_key", sa.String(80), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("process_key", "queue_key", name="uq_workflow_queues_process_key"),
    )
    op.create_index("ix_workflow_queues_process_key", "workflow_queues", ["process_key"])

    op.create_table(
        "workflow_queue_members",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("queue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_queues.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("queue_id", "user_id", name="uq_workflow_queue_members_user"),
    )
    op.create_index("ix_workflow_queue_members_queue_id", "workflow_queue_members", ["queue_id"])
    op.create_index("ix_workflow_queue_members_user_id", "workflow_queue_members", ["user_id"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("process_key", sa.String(80), nullable=False),
        sa.Column("definition_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_definitions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("definition_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("subject_type", sa.String(80), nullable=False),
        sa.Column("subject_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="open"),
        sa.Column("current_step_key", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_instances_process_key", "workflow_instances", ["process_key"])
    op.create_index("ix_workflow_instances_subject", "workflow_instances", ["subject_type", "subject_id"])

    op.create_table(
        "workflow_instance_steps",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_key", sa.String(80), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("queue_key", sa.String(80), nullable=True),
        sa.Column("required_actions", postgresql.JSONB(), nullable=True),
        sa.Column("on_approve_status", sa.String(40), nullable=True),
        sa.Column("entry_condition", sa.String(200), nullable=True),
        sa.Column("skippable", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_instance_steps_instance_id", "workflow_instance_steps", ["instance_id"])

    op.add_column("submittals", sa.Column("submittal_number", sa.String(80), nullable=True))
    op.add_column("submittals", sa.Column("trade", sa.String(40), nullable=True))
    op.add_column("submittals", sa.Column("action_type", sa.String(20), nullable=False, server_default="action"))
    op.add_column("submittals", sa.Column("vendor_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("assigned_reviewer_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("workflow_instance_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("current_revision_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("spec_requirements", postgresql.JSONB(), nullable=True))
    op.add_column("submittals", sa.Column("linked_drawing_ids", postgresql.JSONB(), nullable=True))
    op.add_column("submittals", sa.Column("rfp_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("rfp_response_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("needed_by_date", sa.Date(), nullable=True))
    op.add_column("submittals", sa.Column("internally_reviewed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("submitted_to_ae_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("ae_action", sa.String(80), nullable=True))
    op.add_column("submittals", sa.Column("ae_action_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submittals", sa.Column("notes", sa.Text(), nullable=True))
    op.add_column("submittals", sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("updated_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("submittals", sa.Column("public_token", sa.String(64), nullable=True))
    op.add_column("submittals", sa.Column("public_token_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_submittals_submittal_number", "submittals", ["submittal_number"])
    op.create_index("ix_submittals_trade", "submittals", ["trade"])
    op.create_index("ix_submittals_vendor_id", "submittals", ["vendor_id"])
    op.create_index("ix_submittals_assigned_reviewer_id", "submittals", ["assigned_reviewer_id"])
    op.create_index("ix_submittals_needed_by_date", "submittals", ["needed_by_date"])
    op.create_index("ix_submittals_public_token", "submittals", ["public_token"], unique=True)
    op.create_foreign_key("fk_submittals_vendor_id", "submittals", "companies", ["vendor_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_submittals_assigned_reviewer_id", "submittals", "users", ["assigned_reviewer_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_submittals_workflow_instance_id", "submittals", "workflow_instances", ["workflow_instance_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_submittals_rfp_id", "submittals", "rfps", ["rfp_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_submittals_created_by", "submittals", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_submittals_updated_by", "submittals", "users", ["updated_by_user_id"], ["id"], ondelete="SET NULL")

    op.create_table(
        "submittal_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("submittal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submittals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("revision", sa.String(20), nullable=False, server_default="A"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("package_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("completeness_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_review_annotation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drawing_annotations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("ai_status", sa.String(20), nullable=False, server_default="not_run"),
        sa.Column("ai_overridden_reason", sa.Text(), nullable=True),
        sa.Column("ai_findings", postgresql.JSONB(), nullable=True),
        sa.Column("raw_response", sa.Text(), nullable=True),
        sa.Column("human_stamp", sa.String(40), nullable=True),
        sa.Column("stamp_comments", sa.Text(), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("checklist_complete", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rubber_stamp_suspect", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rush_exception", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("rush_exception_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rush_exception_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_submittal_revisions_submittal_id", "submittal_revisions", ["submittal_id"])
    op.create_foreign_key(
        "fk_submittals_current_revision",
        "submittals",
        "submittal_revisions",
        ["current_revision_id"],
        ["id"],
        ondelete="SET NULL",
        use_alter=True,
    )

    op.create_table(
        "submittal_revision_documents",
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submittal_revisions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "submittal_estimate_line_items",
        sa.Column("submittal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submittals.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("estimate_line_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("estimate_line_items.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "submittal_checklist_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("revision_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submittal_revisions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_key", sa.String(80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(500), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("result", sa.String(20), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("source", sa.String(20), nullable=False, server_default="template"),
        sa.Column("ai_finding_ref", sa.String(80), nullable=True),
        sa.Column("disposition", sa.String(40), nullable=True),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_submittal_checklist_items_revision_id", "submittal_checklist_items", ["revision_id"])

    op.create_table(
        "submittal_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("submittal_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("submittals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("hold_type", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_submittal_holds_submittal_id", "submittal_holds", ["submittal_id"])

    op.add_column("commitment_line_items", sa.Column("submittal_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column(
        "commitment_line_items",
        sa.Column("submittal_release_required", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_commitment_line_items_submittal_id", "commitment_line_items", ["submittal_id"])
    op.create_foreign_key(
        "fk_commitment_line_items_submittal_id",
        "commitment_line_items",
        "submittals",
        ["submittal_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for value in (
        "assignment",
        "ai_run",
        "checklist",
        "stamp",
        "revision",
        "hold_release",
        "ae_action",
        "completeness",
        "transmit",
    ):
        op.execute(sa.text(f"ALTER TYPE submittal_audit_action ADD VALUE IF NOT EXISTS '{value}'"))


def downgrade() -> None:
    op.drop_constraint("fk_commitment_line_items_submittal_id", "commitment_line_items", type_="foreignkey")
    op.drop_index("ix_commitment_line_items_submittal_id", table_name="commitment_line_items")
    op.drop_column("commitment_line_items", "submittal_release_required")
    op.drop_column("commitment_line_items", "submittal_id")
    op.drop_table("submittal_holds")
    op.drop_table("submittal_checklist_items")
    op.drop_table("submittal_estimate_line_items")
    op.drop_table("submittal_revision_documents")
    op.drop_constraint("fk_submittals_current_revision", "submittals", type_="foreignkey")
    op.drop_table("submittal_revisions")
    op.drop_constraint("fk_submittals_updated_by", "submittals", type_="foreignkey")
    op.drop_constraint("fk_submittals_created_by", "submittals", type_="foreignkey")
    op.drop_constraint("fk_submittals_rfp_id", "submittals", type_="foreignkey")
    op.drop_constraint("fk_submittals_workflow_instance_id", "submittals", type_="foreignkey")
    op.drop_constraint("fk_submittals_assigned_reviewer_id", "submittals", type_="foreignkey")
    op.drop_constraint("fk_submittals_vendor_id", "submittals", type_="foreignkey")
    op.drop_index("ix_submittals_public_token", table_name="submittals")
    op.drop_index("ix_submittals_needed_by_date", table_name="submittals")
    op.drop_index("ix_submittals_assigned_reviewer_id", table_name="submittals")
    op.drop_index("ix_submittals_vendor_id", table_name="submittals")
    op.drop_index("ix_submittals_trade", table_name="submittals")
    op.drop_index("ix_submittals_submittal_number", table_name="submittals")
    for col in (
        "public_token_expires_at",
        "public_token",
        "updated_by_user_id",
        "created_by_user_id",
        "notes",
        "released_at",
        "ae_action_at",
        "ae_action",
        "submitted_to_ae_at",
        "internally_reviewed_at",
        "needed_by_date",
        "rfp_response_id",
        "rfp_id",
        "linked_drawing_ids",
        "spec_requirements",
        "current_revision_id",
        "workflow_instance_id",
        "assigned_reviewer_id",
        "vendor_id",
        "action_type",
        "trade",
        "submittal_number",
    ):
        op.drop_column("submittals", col)
    op.drop_table("workflow_instance_steps")
    op.drop_table("workflow_instances")
    op.drop_table("workflow_queue_members")
    op.drop_table("workflow_queues")
    op.drop_table("workflow_definition_steps")
    op.drop_table("workflow_definitions")
    op.drop_column("projects", "allow_po_without_submittal")
    op.drop_column("projects", "require_ae_before_release")
