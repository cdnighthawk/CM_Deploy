"""material_pricing: manufacturer product URL.

Revision ID: 0118_mat_mfr_url
Revises: 0117_mat_depth
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0118_mat_mfr_url"
down_revision: Union[str, Sequence[str], None] = "0117_mat_depth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    cols = {c["name"] for c in sa.inspect(bind).get_columns("material_pricing")}
    if "manufacturer_url" not in cols:
        op.add_column(
            "material_pricing",
            sa.Column("manufacturer_url", sa.String(length=1024), nullable=True),
        )
    op.execute(
        sa.text(
            """
            UPDATE material_pricing
            SET
                manufacturer_url = left(substring(description from 'https?://\\S+$'), 1024),
                description = nullif(
                    trim(both from regexp_replace(
                        description,
                        '\\s*(?:\\|\\s*)?(https?://\\S+)$',
                        '',
                        'i'
                    )),
                    ''
                )
            WHERE manufacturer_url IS NULL
              AND description ~* 'https?://\\S+$'
            """
        )
    )


def downgrade() -> None:
    op.drop_column("material_pricing", "manufacturer_url")
