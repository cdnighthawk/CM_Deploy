"""Link signed I-9 / W-4 HTML documents on hire applications."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0051_hire_signed_form_documents"
down_revision: Union[str, Sequence[str], None] = "0050_remove_hr_demo_seed"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "hr_hire_applications",
        sa.Column("i9_signed_document_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "hr_hire_applications",
        sa.Column("w4_signed_document_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_hr_hire_applications_i9_signed_document_id",
        "hr_hire_applications",
        "documents",
        ["i9_signed_document_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_hr_hire_applications_w4_signed_document_id",
        "hr_hire_applications",
        "documents",
        ["w4_signed_document_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_hr_hire_applications_w4_signed_document_id",
        "hr_hire_applications",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_hr_hire_applications_i9_signed_document_id",
        "hr_hire_applications",
        type_="foreignkey",
    )
    op.drop_column("hr_hire_applications", "w4_signed_document_id")
    op.drop_column("hr_hire_applications", "i9_signed_document_id")
