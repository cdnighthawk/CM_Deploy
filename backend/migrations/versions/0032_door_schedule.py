"""Door schedule: openings, hardware sets, takeoff line links.

Revision ID: 0032_door_schedule
Revises: 0031_takeoff_location_material_catalog
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0032_door_schedule"
down_revision: Union[str, Sequence[str], None] = "0031_takeoff_location_material_catalog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _uuid():
    return postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "door_hardware_sets",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=255), server_default="", nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_door_hardware_sets_code"),
    )
    op.create_index("ix_door_hardware_sets_code", "door_hardware_sets", ["code"])

    op.create_table(
        "door_hardware_set_items",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("hardware_set_id", _uuid(), nullable=False),
        sa.Column("label", sa.String(length=255), server_default="", nullable=False),
        sa.Column("cost_type", sa.String(length=20), server_default="M", nullable=False),
        sa.Column("default_qty", sa.Numeric(15, 4), server_default="1", nullable=False),
        sa.Column("unit", sa.String(length=50), server_default="EA", nullable=False),
        sa.Column("material_pricing_id", _uuid(), nullable=True),
        sa.Column("default_unit_cost", sa.Numeric(15, 4), server_default="0", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.ForeignKeyConstraint(["hardware_set_id"], ["door_hardware_sets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["material_pricing_id"], ["material_pricing.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_door_hardware_set_items_hardware_set_id", "door_hardware_set_items", ["hardware_set_id"])

    op.create_table(
        "door_openings",
        sa.Column("id", _uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("lead_estimate_id", _uuid(), nullable=False),
        sa.Column("project_id", _uuid(), nullable=True),
        sa.Column("mark", sa.String(length=60), server_default="", nullable=False),
        sa.Column("room", sa.String(length=255), nullable=True),
        sa.Column("width", sa.String(length=40), nullable=True),
        sa.Column("height", sa.String(length=40), nullable=True),
        sa.Column("door_type", sa.String(length=120), nullable=True),
        sa.Column("frame_type", sa.String(length=120), nullable=True),
        sa.Column("hardware_set_code", sa.String(length=60), nullable=True),
        sa.Column("fire_rating", sa.String(length=60), nullable=True),
        sa.Column("handing", sa.String(length=60), nullable=True),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("import_batch_id", _uuid(), nullable=True),
        sa.Column("source_row", postgresql.JSONB(), nullable=True),
        sa.ForeignKeyConstraint(["lead_estimate_id"], ["lead_estimates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lead_estimate_id", "mark", name="uq_door_openings_lead_mark"),
    )
    op.create_index("ix_door_openings_lead_estimate_id", "door_openings", ["lead_estimate_id"])
    op.create_index("ix_door_openings_project_id", "door_openings", ["project_id"])
    op.create_index("ix_door_openings_hardware_set_code", "door_openings", ["hardware_set_code"])
    op.create_index("ix_door_openings_import_batch_id", "door_openings", ["import_batch_id"])

    op.add_column("takeoff_line_items", sa.Column("door_opening_id", _uuid(), nullable=True))
    op.add_column("takeoff_line_items", sa.Column("line_role", sa.String(length=40), nullable=True))
    op.create_index("ix_takeoff_line_items_door_opening_id", "takeoff_line_items", ["door_opening_id"])
    op.create_index("ix_takeoff_line_items_line_role", "takeoff_line_items", ["line_role"])
    op.create_foreign_key(
        "fk_takeoff_line_items_door_opening_id",
        "takeoff_line_items",
        "door_openings",
        ["door_opening_id"],
        ["id"],
        ondelete="CASCADE",
    )

    hw_sets = sa.table(
        "door_hardware_sets",
        sa.column("id", _uuid()),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("description", sa.String),
    )
    hw_items = sa.table(
        "door_hardware_set_items",
        sa.column("id", _uuid()),
        sa.column("hardware_set_id", _uuid()),
        sa.column("label", sa.String),
        sa.column("cost_type", sa.String),
        sa.column("default_qty", sa.Numeric),
        sa.column("unit", sa.String),
        sa.column("default_unit_cost", sa.Numeric),
        sa.column("sort_order", sa.Integer),
    )
    conn = op.get_bind()
    import uuid as _uuid_mod

    hw1_id = _uuid_mod.uuid4()
    hw2_id = _uuid_mod.uuid4()
    conn.execute(
        hw_sets.insert(),
        [
            {"id": hw1_id, "code": "HW-1", "name": "Standard office", "description": "Hinge, lock, closer"},
            {"id": hw2_id, "code": "HW-2", "name": "Storefront entry", "description": "Heavy-duty hardware"},
        ],
    )
    conn.execute(
        hw_items.insert(),
        [
            {
                "id": _uuid_mod.uuid4(),
                "hardware_set_id": hw1_id,
                "label": "Hinge (pair)",
                "cost_type": "M",
                "default_qty": 3,
                "unit": "EA",
                "default_unit_cost": 12,
                "sort_order": 0,
            },
            {
                "id": _uuid_mod.uuid4(),
                "hardware_set_id": hw1_id,
                "label": "Cylindrical lockset",
                "cost_type": "M",
                "default_qty": 1,
                "unit": "EA",
                "default_unit_cost": 85,
                "sort_order": 1,
            },
            {
                "id": _uuid_mod.uuid4(),
                "hardware_set_id": hw1_id,
                "label": "Surface closer",
                "cost_type": "M",
                "default_qty": 1,
                "unit": "EA",
                "default_unit_cost": 120,
                "sort_order": 2,
            },
            {
                "id": _uuid_mod.uuid4(),
                "hardware_set_id": hw2_id,
                "label": "Continuous hinge",
                "cost_type": "M",
                "default_qty": 1,
                "unit": "EA",
                "default_unit_cost": 210,
                "sort_order": 0,
            },
            {
                "id": _uuid_mod.uuid4(),
                "hardware_set_id": hw2_id,
                "label": "Exit device",
                "cost_type": "M",
                "default_qty": 1,
                "unit": "EA",
                "default_unit_cost": 450,
                "sort_order": 1,
            },
        ],
    )


def downgrade() -> None:
    op.drop_constraint("fk_takeoff_line_items_door_opening_id", "takeoff_line_items", type_="foreignkey")
    op.drop_index("ix_takeoff_line_items_line_role", table_name="takeoff_line_items")
    op.drop_index("ix_takeoff_line_items_door_opening_id", table_name="takeoff_line_items")
    op.drop_column("takeoff_line_items", "line_role")
    op.drop_column("takeoff_line_items", "door_opening_id")
    op.drop_table("door_openings")
    op.drop_table("door_hardware_set_items")
    op.drop_table("door_hardware_sets")
