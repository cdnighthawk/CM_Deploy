"""material_pricing: buy-from supplier company for catalog emails.

Revision ID: 0114_mat_supplier
Revises: 0113_orgs
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0114_mat_supplier"
down_revision: Union[str, Sequence[str], None] = "0113_orgs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "material_pricing",
        sa.Column("supplier_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(
        "ix_material_pricing_supplier_company_id",
        "material_pricing",
        ["supplier_company_id"],
    )
    op.create_foreign_key(
        "fk_material_pricing_supplier_company_id_companies",
        "material_pricing",
        "companies",
        ["supplier_company_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_material_pricing_supplier_company_id_companies",
        "material_pricing",
        type_="foreignkey",
    )
    op.drop_index("ix_material_pricing_supplier_company_id", table_name="material_pricing")
    op.drop_column("material_pricing", "supplier_company_id")
