"""HRMS expense tracker: project allocation, settlement fields, receipt metadata."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0053_hrms_expense_tracker"
down_revision: Union[str, Sequence[str], None] = "0052_hire_path_job_offer"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hrms_expense_reports", sa.Column("rejection_reason", sa.Text(), nullable=True))
    op.add_column(
        "hrms_expense_reports",
        sa.Column("exported_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("hrms_expense_reports", sa.Column("export_batch_id", sa.UUID(), nullable=True))
    op.add_column(
        "hrms_expense_reports",
        sa.Column("reimbursed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("hrms_expense_reports", sa.Column("reimbursed_by_user_id", sa.UUID(), nullable=True))
    op.create_foreign_key(
        "fk_hrms_expense_reports_reimbursed_by_user_id",
        "hrms_expense_reports",
        "users",
        ["reimbursed_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_hrms_expense_reports_status", "hrms_expense_reports", ["status"], unique=False)

    op.add_column("hrms_expense_lines", sa.Column("project_id", sa.UUID(), nullable=True))
    op.add_column("hrms_expense_lines", sa.Column("merchant", sa.String(length=255), nullable=True))
    op.create_foreign_key(
        "fk_hrms_expense_lines_project_id",
        "hrms_expense_lines",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_hrms_expense_lines_project_id", "hrms_expense_lines", ["project_id"], unique=False)
    op.execute(sa.text("DELETE FROM hrms_expense_lines WHERE project_id IS NULL"))
    op.alter_column("hrms_expense_lines", "project_id", nullable=False)


def downgrade() -> None:
    op.alter_column("hrms_expense_lines", "project_id", nullable=True)
    op.drop_index("ix_hrms_expense_lines_project_id", table_name="hrms_expense_lines")
    op.drop_constraint("fk_hrms_expense_lines_project_id", "hrms_expense_lines", type_="foreignkey")
    op.drop_column("hrms_expense_lines", "merchant")
    op.drop_column("hrms_expense_lines", "project_id")

    op.drop_index("ix_hrms_expense_reports_status", table_name="hrms_expense_reports")
    op.drop_constraint(
        "fk_hrms_expense_reports_reimbursed_by_user_id",
        "hrms_expense_reports",
        type_="foreignkey",
    )
    op.drop_column("hrms_expense_reports", "reimbursed_by_user_id")
    op.drop_column("hrms_expense_reports", "reimbursed_at")
    op.drop_column("hrms_expense_reports", "export_batch_id")
    op.drop_column("hrms_expense_reports", "exported_at")
    op.drop_column("hrms_expense_reports", "rejection_reason")
