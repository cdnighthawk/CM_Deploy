"""HR employee pay scales and document links (Plan 19 extension)."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

revision: str = "0024_hr_pay_docs"
down_revision: Union[str, Sequence[str], None] = "0023_safety_training_records"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

JAMIE_ID = "a1700000-0000-4000-8000-000000000001"
DEMO_PAY_1 = "d1700000-0000-4000-8000-000000000001"
DEMO_PAY_2 = "d1700000-0000-4000-8000-000000000002"
DEMO_HR_DOC_1 = "d1700000-0000-4000-8000-000000000011"


def upgrade() -> None:
    op.create_table(
        "hr_employee_pay_scales",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("pay_basis", sa.String(32), nullable=False),
        sa.Column("hourly_rate", sa.Numeric(12, 4), nullable=True),
        sa.Column("annual_salary", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("wage_rate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["wage_rate_id"], ["wage_rates.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hr_employee_pay_scales_user_id", "hr_employee_pay_scales", ["user_id"], unique=False)
    op.create_index(
        "ix_hr_employee_pay_scales_user_sort",
        "hr_employee_pay_scales",
        ["user_id", "sort_order"],
        unique=False,
    )

    op.create_table(
        "hr_employee_documents",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_hr_employee_documents_user_id", "hr_employee_documents", ["user_id"], unique=False)

    conn = op.get_bind()
    conn.execute(
        text(
            """
            INSERT INTO hr_employee_pay_scales (
                id, user_id, sort_order, label, pay_basis, hourly_rate, annual_salary, currency,
                effective_from, effective_to, wage_rate_id, document_id, notes, created_at, updated_at
            ) VALUES (
                CAST(:id1 AS uuid),
                CAST(:jamie AS uuid),
                0,
                'Field journeyman (standard)',
                'hourly',
                58.5000,
                NULL,
                'USD',
                CURRENT_DATE - 400,
                NULL,
                NULL,
                NULL,
                'Demo pay scale row.',
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id1": DEMO_PAY_1, "jamie": JAMIE_ID},
    )
    conn.execute(
        text(
            """
            INSERT INTO hr_employee_pay_scales (
                id, user_id, sort_order, label, pay_basis, hourly_rate, annual_salary, currency,
                effective_from, effective_to, wage_rate_id, document_id, notes, created_at, updated_at
            ) VALUES (
                CAST(:id2 AS uuid),
                CAST(:jamie AS uuid),
                1,
                'Foreman differential',
                'hourly',
                7.2500,
                NULL,
                'USD',
                CURRENT_DATE - 200,
                NULL,
                NULL,
                NULL,
                'Additive hourly bump when acting foreman.',
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id2": DEMO_PAY_2, "jamie": JAMIE_ID},
    )
    conn.execute(
        text(
            """
            INSERT INTO hr_employee_documents (
                id, user_id, category, title, sort_order, document_id, created_at, updated_at
            ) VALUES (
                CAST(:id3 AS uuid),
                CAST(:jamie AS uuid),
                'offer_letter',
                'Signed offer letter (2025)',
                0,
                NULL,
                NOW(),
                NOW()
            )
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"id3": DEMO_HR_DOC_1, "jamie": JAMIE_ID},
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        text(
            "DELETE FROM hr_employee_documents WHERE id = CAST(:id3 AS uuid)"
        ),
        {"id3": DEMO_HR_DOC_1},
    )
    conn.execute(
        text(
            "DELETE FROM hr_employee_pay_scales WHERE id IN (CAST(:id1 AS uuid), CAST(:id2 AS uuid))"
        ),
        {"id1": DEMO_PAY_1, "id2": DEMO_PAY_2},
    )
    op.drop_index("ix_hr_employee_documents_user_id", table_name="hr_employee_documents")
    op.drop_table("hr_employee_documents")
    op.drop_index("ix_hr_employee_pay_scales_user_sort", table_name="hr_employee_pay_scales")
    op.drop_index("ix_hr_employee_pay_scales_user_id", table_name="hr_employee_pay_scales")
    op.drop_table("hr_employee_pay_scales")
