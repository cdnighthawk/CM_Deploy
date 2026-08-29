"""Daily reports and field photos for the Android / Expo field app.

Revision ID: 0069_field_daily_reports_photos
Revises: 0068_company_office_coords
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0069_field_daily_reports_photos"
down_revision: Union[str, Sequence[str], None] = "0068_company_office_coords"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FIELD_ANNOTATION_TYPES = ("cloud", "arrow", "highlight", "text_note", "photo_pin")


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "daily_reports" not in tables:
        op.create_table(
            "daily_reports",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("report_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
            sa.Column("sections", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "report_date", name="uq_daily_reports_project_date"),
        )
        op.create_index("ix_daily_reports_project_id", "daily_reports", ["project_id"])
        op.create_index("ix_daily_reports_report_date", "daily_reports", ["report_date"])

    if "field_photos" not in tables:
        op.create_table(
            "field_photos",
            sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
            sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("daily_report_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("drawing_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
            sa.Column("caption", sa.Text(), nullable=True),
            sa.Column("location_text", sa.String(length=300), nullable=True),
            sa.Column("taken_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("lat", sa.Numeric(10, 7), nullable=True),
            sa.Column("lon", sa.Numeric(10, 7), nullable=True),
            sa.Column("original_filename", sa.String(length=300), nullable=True),
            sa.Column("mime_type", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["daily_report_id"], ["daily_reports.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["drawing_id"], ["drawings.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_field_photos_project_id", "field_photos", ["project_id"])
        op.create_index("ix_field_photos_daily_report_id", "field_photos", ["daily_report_id"])
        op.create_index("ix_field_photos_drawing_id", "field_photos", ["drawing_id"])

    enums = {e["name"] for e in insp.get_enums()} if hasattr(insp, "get_enums") else set()
    if "annotation_type" in enums or True:
        for val in _FIELD_ANNOTATION_TYPES:
            op.execute(sa.text(f"ALTER TYPE annotation_type ADD VALUE IF NOT EXISTS '{val}'"))


def downgrade() -> None:
    op.drop_index("ix_field_photos_drawing_id", table_name="field_photos")
    op.drop_index("ix_field_photos_daily_report_id", table_name="field_photos")
    op.drop_index("ix_field_photos_project_id", table_name="field_photos")
    op.drop_table("field_photos")
    op.drop_index("ix_daily_reports_report_date", table_name="daily_reports")
    op.drop_index("ix_daily_reports_project_id", table_name="daily_reports")
    op.drop_table("daily_reports")
