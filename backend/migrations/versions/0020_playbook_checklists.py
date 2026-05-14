"""Operational playbook checklist templates and runs."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0020_playbook_checklists"
down_revision: Union[str, Sequence[str], None] = "0019_estimates_due_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

run_status = postgresql.ENUM("open", "complete", "cancelled", name="checklist_run_status", create_type=False)
step_status = postgresql.ENUM("pending", "done", "skipped", name="checklist_run_step_status", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    run_status.create(bind, checkfirst=True)
    step_status.create(bind, checkfirst=True)

    op.create_table(
        "checklist_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_checklist_templates_company_id", "checklist_templates", ["company_id"], unique=False)

    op.create_table(
        "checklist_template_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("default_assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["default_assignee_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_checklist_template_steps_template_id", "checklist_template_steps", ["template_id"], unique=False)
    op.create_index(
        "ix_checklist_template_steps_tpl_seq",
        "checklist_template_steps",
        ["template_id", "sequence"],
        unique=False,
    )

    op.create_table(
        "checklist_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", run_status, nullable=False, server_default="open"),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_checklist_runs_template_id", "checklist_runs", ["template_id"], unique=False)
    op.create_index("ix_checklist_runs_project_id", "checklist_runs", ["project_id"], unique=False)

    op.create_table(
        "checklist_run_steps",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("assignee_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", step_status, nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["checklist_runs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["assignee_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["completed_by_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_checklist_run_steps_run_id", "checklist_run_steps", ["run_id"], unique=False)
    op.create_index(
        "ix_checklist_run_steps_run_seq",
        "checklist_run_steps",
        ["run_id", "sequence"],
        unique=False,
    )
    op.create_index(
        "ix_checklist_run_steps_assignee_status",
        "checklist_run_steps",
        ["assignee_user_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_checklist_run_steps_assignee_status", table_name="checklist_run_steps")
    op.drop_index("ix_checklist_run_steps_run_seq", table_name="checklist_run_steps")
    op.drop_index("ix_checklist_run_steps_run_id", table_name="checklist_run_steps")
    op.drop_table("checklist_run_steps")

    op.drop_index("ix_checklist_runs_project_id", table_name="checklist_runs")
    op.drop_index("ix_checklist_runs_template_id", table_name="checklist_runs")
    op.drop_table("checklist_runs")

    op.drop_index("ix_checklist_template_steps_tpl_seq", table_name="checklist_template_steps")
    op.drop_index("ix_checklist_template_steps_template_id", table_name="checklist_template_steps")
    op.drop_table("checklist_template_steps")

    op.drop_index("ix_checklist_templates_company_id", table_name="checklist_templates")
    op.drop_table("checklist_templates")

    bind = op.get_bind()
    step_status.drop(bind, checkfirst=True)
    run_status.drop(bind, checkfirst=True)
