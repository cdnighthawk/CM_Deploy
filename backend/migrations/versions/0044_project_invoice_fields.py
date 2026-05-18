"""Project invoicing fields and company invoice delivery methods."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision: str = "0044_project_invoice_fields"
down_revision: Union[str, Sequence[str], None] = "0043_role_module_permissions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "invoice_delivery_methods",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_invoice_delivery_methods_code"),
    )
    op.create_index("ix_invoice_delivery_methods_code", "invoice_delivery_methods", ["code"], unique=True)

    op.add_column("projects", sa.Column("invoice_method", sa.String(80), nullable=True))
    op.add_column("projects", sa.Column("invoice_due_date", sa.Date(), nullable=True))
    op.add_column("projects", sa.Column("invoice_recipient_emails", sa.Text(), nullable=True))
    op.create_index("ix_projects_invoice_method", "projects", ["invoice_method"], unique=False)

    conn = op.get_bind()
    for code, label in (("textura", "Textura"), ("email", "Email")):
        conn.execute(
            text(
                """
                INSERT INTO invoice_delivery_methods (code, label, is_system)
                VALUES (:code, :label, true)
                ON CONFLICT (code) DO NOTHING
                """
            ),
            {"code": code, "label": label},
        )


def downgrade() -> None:
    op.drop_index("ix_projects_invoice_method", table_name="projects")
    op.drop_column("projects", "invoice_recipient_emails")
    op.drop_column("projects", "invoice_due_date")
    op.drop_column("projects", "invoice_method")
    op.drop_index("ix_invoice_delivery_methods_code", table_name="invoice_delivery_methods")
    op.drop_table("invoice_delivery_methods")
