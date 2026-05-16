"""material_pricing.csi_spec_section; rename HW-* hardware sets to HD-*.

Revision ID: 0033_material_csi_hd_rename
Revises: 0032_door_schedule
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_material_csi_hd_rename"
down_revision: Union[str, Sequence[str], None] = "0032_door_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "material_pricing",
        sa.Column("csi_spec_section", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_material_pricing_csi_spec_section",
        "material_pricing",
        ["csi_spec_section"],
    )

    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE door_hardware_sets SET code = 'HD-1' WHERE code = 'HW-1'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE door_hardware_sets SET code = 'HD-2' WHERE code = 'HW-2'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE door_openings SET hardware_set_code = 'HD-1'
            WHERE UPPER(TRIM(hardware_set_code)) = 'HW-1'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE door_openings SET hardware_set_code = 'HD-2'
            WHERE UPPER(TRIM(hardware_set_code)) = 'HW-2'
            """
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            UPDATE door_openings SET hardware_set_code = 'HW-1'
            WHERE UPPER(TRIM(hardware_set_code)) = 'HD-1'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE door_openings SET hardware_set_code = 'HW-2'
            WHERE UPPER(TRIM(hardware_set_code)) = 'HD-2'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE door_hardware_sets SET code = 'HW-1' WHERE code = 'HD-1'
            """
        )
    )
    conn.execute(
        sa.text(
            """
            UPDATE door_hardware_sets SET code = 'HW-2' WHERE code = 'HD-2'
            """
        )
    )
    op.drop_index("ix_material_pricing_csi_spec_section", table_name="material_pricing")
    op.drop_column("material_pricing", "csi_spec_section")
