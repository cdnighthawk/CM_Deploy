"""Company offices plus job shipping destination and expected install date.

Revision ID: 0095_office_ship
Revises: 0094_vendor_line
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0095_office_ship"
down_revision: Union[str, Sequence[str], None] = "0094_vendor_line"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "company_offices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False, server_default="Office"),
        sa.Column("address_line1", sa.String(length=255), nullable=True),
        sa.Column("address_line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=120), nullable=True),
        sa.Column("state", sa.String(length=50), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True, server_default="US"),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_company_offices_company_id", "company_offices", ["company_id"])

    op.add_column("projects", sa.Column("expected_install_date", sa.Date(), nullable=True))
    op.add_column(
        "projects",
        sa.Column("ship_to_kind", sa.String(length=20), nullable=False, server_default="jobsite"),
    )
    op.add_column(
        "projects",
        sa.Column(
            "ship_to_office_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("company_offices.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_projects_ship_to_office_id", "projects", ["ship_to_office_id"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO company_offices (
                company_id, name, address_line1, address_line2, city, state, postal_code,
                country, latitude, longitude, is_default, sort_order
            )
            SELECT
                c.id,
                COALESCE(NULLIF(BTRIM(c.city), ''), NULLIF(BTRIM(c.name), ''), 'Main office'),
                c.address_line1,
                c.address_line2,
                c.city,
                c.state,
                c.postal_code,
                COALESCE(c.country, 'US'),
                c.latitude,
                c.longitude,
                true,
                0
            FROM companies c
            WHERE c.company_type = 'self'
              AND c.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1 FROM company_offices o WHERE o.company_id = c.id
              )
              AND (
                  c.address_line1 IS NOT NULL
                  OR c.city IS NOT NULL
                  OR c.postal_code IS NOT NULL
                  OR c.latitude IS NOT NULL
              )
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_projects_ship_to_office_id", table_name="projects")
    op.drop_column("projects", "ship_to_office_id")
    op.drop_column("projects", "ship_to_kind")
    op.drop_column("projects", "expected_install_date")
    op.drop_index("ix_company_offices_company_id", table_name="company_offices")
    op.drop_table("company_offices")
