"""Store geocoded office coordinates on companies.

Revision ID: 0068_company_office_coords
Revises: 0067_import_github_feedback_12_16
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0068_company_office_coords"
down_revision: Union[str, Sequence[str], None] = "0067_import_github_feedback_12_16"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    cols = {c["name"] for c in insp.get_columns("companies")}
    if "latitude" not in cols:
        op.add_column("companies", sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
    if "longitude" not in cols:
        op.add_column("companies", sa.Column("longitude", sa.Numeric(9, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("companies", "longitude")
    op.drop_column("companies", "latitude")
