"""Store material_pricing.csi_spec_section as 6-digit codes.

Older catalog loads kept display spacing (``10 11 00``). The Division filter
normalizes the dropdown value to ``101100``, so those rows disappeared.

Revision ID: 0110_mat_csi
Revises: 0109_mat_size
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0110_mat_csi"
down_revision: Union[str, Sequence[str], None] = "0109_mat_size"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            UPDATE material_pricing
            SET csi_spec_section = REPLACE(csi_spec_section, ' ', '')
            WHERE csi_spec_section LIKE '% %'
              AND LENGTH(REPLACE(csi_spec_section, ' ', '')) = 6
            """
        )
    )


def downgrade() -> None:
    pass
