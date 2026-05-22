"""Hire path (union dispatch vs standard) and job offer fields."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0052_hire_path_job_offer"
down_revision: Union[str, Sequence[str], None] = "0051_hire_signed_form_documents"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("hr_hire_applications", sa.Column("hire_path", sa.String(length=32), nullable=True))
    op.add_column("hr_hire_applications", sa.Column("offer_position", sa.String(length=500), nullable=True))
    op.add_column("hr_hire_applications", sa.Column("offer_pay_description", sa.Text(), nullable=True))
    op.add_column("hr_hire_applications", sa.Column("offer_start_date", sa.Date(), nullable=True))
    op.add_column(
        "hr_hire_applications",
        sa.Column("offer_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hr_hire_applications",
        sa.Column("offer_accepted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("hr_hire_applications", sa.Column("offer_document_id", sa.UUID(), nullable=True))
    op.add_column("hr_hire_applications", sa.Column("offer_pending_role_ids", sa.Text(), nullable=True))
    op.create_foreign_key(
        "fk_hr_hire_applications_offer_document_id",
        "hr_hire_applications",
        "documents",
        ["offer_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_hr_hire_applications_hire_path", "hr_hire_applications", ["hire_path"], unique=False)

    # Existing applicants who already started I-9/W-4 keep the full union-style wizard.
    op.execute(
        """
        UPDATE hr_hire_applications
        SET hire_path = 'union_dispatch'
        WHERE hire_path IS NULL
          AND (
            i9_section1_json_encrypted IS NOT NULL
            OR i9_signed_at IS NOT NULL
            OR w4_json_encrypted IS NOT NULL
            OR w4_signed_at IS NOT NULL
          )
        """
    )


def downgrade() -> None:
    op.drop_index("ix_hr_hire_applications_hire_path", table_name="hr_hire_applications")
    op.drop_constraint("fk_hr_hire_applications_offer_document_id", "hr_hire_applications", type_="foreignkey")
    op.drop_column("hr_hire_applications", "offer_pending_role_ids")
    op.drop_column("hr_hire_applications", "offer_document_id")
    op.drop_column("hr_hire_applications", "offer_accepted_at")
    op.drop_column("hr_hire_applications", "offer_sent_at")
    op.drop_column("hr_hire_applications", "offer_start_date")
    op.drop_column("hr_hire_applications", "offer_pay_description")
    op.drop_column("hr_hire_applications", "offer_position")
    op.drop_column("hr_hire_applications", "hire_path")
