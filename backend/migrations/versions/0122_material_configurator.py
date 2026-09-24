"""Configurable catalog SKUs: option schema key + frozen takeoff snapshot.

Revision ID: 0122_mat_cfg
Revises: 0121_line_trade
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0122_mat_cfg"
down_revision: Union[str, Sequence[str], None] = "0121_line_trade"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    mat_cols = {c["name"] for c in sa.inspect(bind).get_columns("material_pricing")}
    if "configurator_key" not in mat_cols:
        op.add_column(
            "material_pricing",
            sa.Column("configurator_key", sa.String(length=80), nullable=True),
        )
        op.create_index(
            "ix_material_pricing_configurator_key",
            "material_pricing",
            ["configurator_key"],
        )
    line_cols = {c["name"] for c in sa.inspect(bind).get_columns("takeoff_line_items")}
    if "configuration_json" not in line_cols:
        op.add_column(
            "takeoff_line_items",
            sa.Column("configuration_json", postgresql.JSONB(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    line_cols = {c["name"] for c in sa.inspect(bind).get_columns("takeoff_line_items")}
    if "configuration_json" in line_cols:
        op.drop_column("takeoff_line_items", "configuration_json")
    mat_indexes = {ix["name"] for ix in sa.inspect(bind).get_indexes("material_pricing")}
    mat_cols = {c["name"] for c in sa.inspect(bind).get_columns("material_pricing")}
    if "ix_material_pricing_configurator_key" in mat_indexes:
        op.drop_index("ix_material_pricing_configurator_key", table_name="material_pricing")
    if "configurator_key" in mat_cols:
        op.drop_column("material_pricing", "configurator_key")
