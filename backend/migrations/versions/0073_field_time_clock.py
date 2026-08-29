"""Field time clock punches and project geofence.

Revision ID: 0073_field_time_clock
Revises: 0072_gs_planroom_detail
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0073_field_time_clock"
down_revision: Union[str, Sequence[str], None] = "0072_gs_planroom_detail"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    project_cols = {c["name"] for c in insp.get_columns("projects")}

    if "latitude" not in project_cols:
        op.add_column("projects", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    if "longitude" not in project_cols:
        op.add_column("projects", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
    if "geofence_radius_m" not in project_cols:
        op.add_column(
            "projects",
            sa.Column("geofence_radius_m", sa.Integer(), nullable=True, server_default="250"),
        )

    if "time_entries" not in tables:
        op.create_table(
            "time_entries",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("cost_code_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("clock_in_photo_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("clock_out_photo_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["cost_code_id"], ["rfi_cost_codes.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["clock_in_photo_id"], ["field_photos.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["clock_out_photo_id"], ["field_photos.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("client_id", name="uq_time_entries_client_id"),
        )
        op.create_index("ix_time_entries_user_id", "time_entries", ["user_id"])
        op.create_index("ix_time_entries_project_id", "time_entries", ["project_id"])
        op.execute(
            sa.text(
                "CREATE UNIQUE INDEX uq_time_entries_one_open ON time_entries (user_id) "
                "WHERE status <> 'closed'"
            )
        )

    if "time_punches" not in tables:
        op.create_table(
            "time_punches",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("entry_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("kind", sa.String(length=20), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("lat", sa.Numeric(10, 7), nullable=True),
            sa.Column("lon", sa.Numeric(10, 7), nullable=True),
            sa.Column("accuracy_m", sa.Numeric(8, 2), nullable=True),
            sa.Column("geofence_ok", sa.Boolean(), nullable=True),
            sa.Column("geofence_distance_m", sa.Numeric(10, 2), nullable=True),
            sa.Column("photo_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("note", sa.Text(), nullable=True),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["entry_id"], ["time_entries.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["photo_id"], ["field_photos.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("client_id", name="uq_time_punches_client_id"),
        )
        op.create_index("ix_time_punches_entry_id", "time_punches", ["entry_id"])


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())
    if "time_punches" in tables:
        op.drop_table("time_punches")
    if "time_entries" in tables:
        op.drop_table("time_entries")
    project_cols = {c["name"] for c in insp.get_columns("projects")}
    if "geofence_radius_m" in project_cols:
        op.drop_column("projects", "geofence_radius_m")
    if "longitude" in project_cols:
        op.drop_column("projects", "longitude")
    if "latitude" in project_cols:
        op.drop_column("projects", "latitude")
