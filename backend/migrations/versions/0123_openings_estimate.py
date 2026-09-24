"""Job-scoped openings workspace: types, hardware sets, takeoff source_kind.

Revision ID: 0123_openings
Revises: 0122_mat_cfg
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0123_openings"
down_revision: Union[str, Sequence[str], None] = "0122_mat_cfg"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _cols(bind, table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(table)}


def _indexes(bind, table: str) -> set[str]:
    return {ix["name"] for ix in sa.inspect(bind).get_indexes(table)}


def _tables(bind) -> set[str]:
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)

    if "spec_trade_map" in tables:
        st_cols = _cols(bind, "spec_trade_map")
        if "trade_group" not in st_cols:
            op.add_column("spec_trade_map", sa.Column("trade_group", sa.String(length=40), nullable=True))
            op.create_index("ix_spec_trade_map_trade_group", "spec_trade_map", ["trade_group"])

    if "door_openings" in tables:
        do_cols = _cols(bind, "door_openings")
        if "estimate_id" not in do_cols:
            op.add_column(
                "door_openings",
                sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=True),
            )
            op.create_index("ix_door_openings_estimate_id", "door_openings", ["estimate_id"])
            op.create_foreign_key(
                "fk_door_openings_estimate_id",
                "door_openings",
                "estimates",
                ["estimate_id"],
                ["id"],
                ondelete="CASCADE",
            )
        extras = [
            ("qty", sa.Column("qty", sa.Numeric(10, 2), nullable=False, server_default="1")),
            ("leaf_count", sa.Column("leaf_count", sa.Numeric(6, 2), nullable=False, server_default="1")),
            ("width_in", sa.Column("width_in", sa.Numeric(8, 2), nullable=True)),
            ("height_in", sa.Column("height_in", sa.Numeric(8, 2), nullable=True)),
            ("thickness_in", sa.Column("thickness_in", sa.Numeric(8, 2), nullable=True)),
            ("hand", sa.Column("hand", sa.String(length=20), nullable=True)),
            ("fire_rating_min", sa.Column("fire_rating_min", sa.Integer(), nullable=True)),
            ("material", sa.Column("material", sa.String(length=40), nullable=True)),
            ("door_type_code", sa.Column("door_type_code", sa.String(length=40), nullable=True)),
            ("frame_type_code", sa.Column("frame_type_code", sa.String(length=40), nullable=True)),
            ("frame_material", sa.Column("frame_material", sa.String(length=40), nullable=True)),
            ("frame_construction", sa.Column("frame_construction", sa.String(length=40), nullable=True)),
            ("wall_thickness_in", sa.Column("wall_thickness_in", sa.Numeric(8, 2), nullable=True)),
            ("frame_gauge", sa.Column("frame_gauge", sa.String(length=10), nullable=True)),
            ("hardware_set_no", sa.Column("hardware_set_no", sa.String(length=60), nullable=True)),
            ("location", sa.Column("location", sa.String(length=255), nullable=True)),
            ("to_room", sa.Column("to_room", sa.String(length=255), nullable=True)),
            ("from_room", sa.Column("from_room", sa.String(length=255), nullable=True)),
            ("elevation", sa.Column("elevation", sa.String(length=80), nullable=True)),
            ("sheet_ref", sa.Column("sheet_ref", sa.String(length=80), nullable=True)),
            ("scope_flag", sa.Column("scope_flag", sa.String(length=20), nullable=False, server_default="in")),
            ("source", sa.Column("source", sa.String(length=40), nullable=False, server_default="manual")),
            ("conflicts", sa.Column("conflicts", postgresql.JSONB(), nullable=True)),
            ("confirmed_at", sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True)),
            ("confirmed_by", sa.Column("confirmed_by", postgresql.UUID(as_uuid=True), nullable=True)),
        ]
        do_cols = _cols(bind, "door_openings")
        for name, col in extras:
            if name not in do_cols:
                op.add_column("door_openings", col)
        do_cols = _cols(bind, "door_openings")
        do_ix = _indexes(bind, "door_openings")
        if "hardware_set_no" in do_cols and "ix_door_openings_hardware_set_no" not in do_ix:
            op.create_index("ix_door_openings_hardware_set_no", "door_openings", ["hardware_set_no"])
        if "confirmed_by" in do_cols:
            fks = {fk["name"] for fk in sa.inspect(bind).get_foreign_keys("door_openings")}
            if "fk_door_openings_confirmed_by" not in fks:
                op.create_foreign_key(
                    "fk_door_openings_confirmed_by",
                    "door_openings",
                    "users",
                    ["confirmed_by"],
                    ["id"],
                    ondelete="SET NULL",
                )
        op.alter_column(
            "door_openings",
            "lead_estimate_id",
            existing_type=postgresql.UUID(as_uuid=True),
            nullable=True,
        )
        uniques = {u["name"] for u in sa.inspect(bind).get_unique_constraints("door_openings")}
        if "uq_door_openings_estimate_mark" not in uniques:
            op.create_unique_constraint(
                "uq_door_openings_estimate_mark",
                "door_openings",
                ["estimate_id", "mark"],
            )

    if "takeoff_line_items" in tables:
        tl_cols = _cols(bind, "takeoff_line_items")
        if "source_kind" not in tl_cols:
            op.add_column(
                "takeoff_line_items",
                sa.Column("source_kind", sa.String(length=40), nullable=True),
            )
            op.create_index("ix_takeoff_line_items_source_kind", "takeoff_line_items", ["source_kind"])

    if "opening_types" not in tables:
        op.create_table(
            "opening_types",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("kind", sa.String(length=20), server_default="door", nullable=False),
            sa.Column("code", sa.String(length=40), server_default="", nullable=False),
            sa.Column("description", sa.String(length=500), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("snapshot", postgresql.JSONB(), nullable=True),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("estimate_id", "kind", "code", name="uq_opening_types_estimate_kind_code"),
        )
        op.create_index("ix_opening_types_estimate_id", "opening_types", ["estimate_id"])
        op.create_index("ix_opening_types_organization_id", "opening_types", ["organization_id"])

    if "hardware_sets" not in tables:
        op.create_table(
            "hardware_sets",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("estimate_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("set_no", sa.String(length=60), server_default="", nullable=False),
            sa.Column("set_no_normalized", sa.String(length=60), server_default="", nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("governs", sa.String(length=20), server_default="spec", nullable=False),
            sa.Column("source_doc_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("finish_default", sa.String(length=40), nullable=True),
            sa.Column("fire_required", sa.Boolean(), nullable=True),
            sa.Column("pair_set", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("electrified", sa.Boolean(), server_default="false", nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("conflicts", postgresql.JSONB(), nullable=True),
            sa.ForeignKeyConstraint(["estimate_id"], ["estimates.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["source_doc_id"], ["documents.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("estimate_id", "set_no_normalized", name="uq_hardware_sets_estimate_set_no"),
        )
        op.create_index("ix_hardware_sets_estimate_id", "hardware_sets", ["estimate_id"])
        op.create_index("ix_hardware_sets_organization_id", "hardware_sets", ["organization_id"])
        op.create_index("ix_hardware_sets_source_doc_id", "hardware_sets", ["source_doc_id"])

    if "hardware_set_items" not in tables:
        op.create_table(
            "hardware_set_items",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("hardware_set_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("seq", sa.Integer(), server_default="0", nullable=False),
            sa.Column("qty", sa.Numeric(15, 4), nullable=False),
            sa.Column("qty_unit", sa.String(length=20), server_default="ea", nullable=False),
            sa.Column("category", sa.String(length=40), server_default="other", nullable=False),
            sa.Column("description", sa.String(length=500), server_default="", nullable=False),
            sa.Column("manufacturer", sa.String(length=200), nullable=True),
            sa.Column("catalog", sa.String(length=200), nullable=True),
            sa.Column("function", sa.String(length=80), nullable=True),
            sa.Column("finish", sa.String(length=40), nullable=True),
            sa.Column("size", sa.String(length=80), nullable=True),
            sa.Column("alternates", postgresql.JSONB(), nullable=True),
            sa.Column("material_pricing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.ForeignKeyConstraint(["hardware_set_id"], ["hardware_sets.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["material_pricing_id"], ["material_pricing.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_hardware_set_items_hardware_set_id", "hardware_set_items", ["hardware_set_id"])
        op.create_index("ix_hardware_set_items_material_pricing_id", "hardware_set_items", ["material_pricing_id"])
        op.create_index("ix_hardware_set_items_organization_id", "hardware_set_items", ["organization_id"])


def downgrade() -> None:
    bind = op.get_bind()
    tables = _tables(bind)
    if "hardware_set_items" in tables:
        op.drop_table("hardware_set_items")
    if "hardware_sets" in tables:
        op.drop_table("hardware_sets")
    if "opening_types" in tables:
        op.drop_table("opening_types")
    if "takeoff_line_items" in tables:
        cols = _cols(bind, "takeoff_line_items")
        ix = _indexes(bind, "takeoff_line_items")
        if "ix_takeoff_line_items_source_kind" in ix:
            op.drop_index("ix_takeoff_line_items_source_kind", table_name="takeoff_line_items")
        if "source_kind" in cols:
            op.drop_column("takeoff_line_items", "source_kind")
