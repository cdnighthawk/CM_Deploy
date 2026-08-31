"""Company-wide master cost codes; seed from existing project codes.

Revision ID: 0086_co_jcc
Revises: 0085_jcc_sage
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0086_co_jcc"
down_revision: Union[str, Sequence[str], None] = "0085_jcc_sage"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_cost_codes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("order_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("units", sa.String(length=40), nullable=True),
        sa.Column("owner_cost_code", sa.String(length=80), nullable=True),
        sa.Column("owner_cost_code_desc", sa.String(length=200), nullable=True),
        sa.Column("default_tax_code", sa.String(length=40), nullable=True),
        sa.Column("division_code", sa.String(length=40), nullable=True),
        sa.Column("division_desc", sa.String(length=200), nullable=True),
        sa.Column("major_code", sa.String(length=40), nullable=True),
        sa.Column("major_desc", sa.String(length=200), nullable=True),
        sa.Column("minor_code", sa.String(length=40), nullable=True),
        sa.Column("minor_desc", sa.String(length=200), nullable=True),
        sa.Column("subminor_code", sa.String(length=40), nullable=True),
        sa.Column("subminor_desc", sa.String(length=200), nullable=True),
        sa.Column("workers_comp_code", sa.String(length=40), nullable=True),
        sa.Column("ap_tax_code", sa.String(length=40), nullable=True),
        sa.Column("ar_tax_code", sa.String(length=40), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_company_cost_codes_code"),
    )
    op.execute(
        """
        INSERT INTO company_cost_codes (
            id, created_at, updated_at, code, description, is_active, order_number, units,
            owner_cost_code, owner_cost_code_desc, default_tax_code,
            division_code, division_desc, major_code, major_desc,
            minor_code, minor_desc, subminor_code, subminor_desc,
            workers_comp_code, ap_tax_code, ar_tax_code
        )
        SELECT DISTINCT ON (code)
            gen_random_uuid(), now(), now(), code,
            COALESCE(NULLIF(description, ''), code),
            COALESCE(is_active, true),
            COALESCE(order_number, 0),
            units, owner_cost_code, owner_cost_code_desc, default_tax_code,
            division_code, division_desc, major_code, major_desc,
            minor_code, minor_desc, subminor_code, subminor_desc,
            workers_comp_code, ap_tax_code, ar_tax_code
        FROM rfi_cost_codes
        WHERE code IS NOT NULL AND BTRIM(code) <> ''
        ORDER BY code, updated_at DESC
        """
    )


def downgrade() -> None:
    op.drop_table("company_cost_codes")
