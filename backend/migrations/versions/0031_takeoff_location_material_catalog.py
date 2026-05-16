"""takeoff_line_items: optional site location + link to material_pricing catalog row.

Revision ID: 0031_takeoff_location_material_catalog
Revises: 0030_hrms_foundation
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0031_takeoff_location_material_catalog"
down_revision: Union[str, Sequence[str], None] = "0030_hrms_foundation"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid():
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    # Alembic default version_num is VARCHAR(32); our revision ids are longer.
    op.execute(
        sa.text("ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(128)")
    )
    op.add_column("takeoff_line_items", sa.Column("takeoff_location", sa.String(length=500), nullable=True))
    op.add_column("takeoff_line_items", sa.Column("material_pricing_id", _uuid(), nullable=True))
    op.create_index("ix_takeoff_line_items_material_pricing_id", "takeoff_line_items", ["material_pricing_id"])
    op.create_foreign_key(
        "fk_takeoff_line_items_material_pricing_id",
        "takeoff_line_items",
        "material_pricing",
        ["material_pricing_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_takeoff_line_items_material_pricing_id", "takeoff_line_items", type_="foreignkey")
    op.drop_index("ix_takeoff_line_items_material_pricing_id", table_name="takeoff_line_items")
    op.drop_column("takeoff_line_items", "material_pricing_id")
    op.drop_column("takeoff_line_items", "takeoff_location")
