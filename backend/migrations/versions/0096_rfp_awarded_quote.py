"""Store the awarded vendor quote on an RFP.

Revision ID: 0096_rfp_award
Revises: 0095_office_ship
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0096_rfp_award"
down_revision: Union[str, Sequence[str], None] = "0095_office_ship"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("rfps", sa.Column("awarded_quote_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_index("ix_rfps_awarded_quote_id", "rfps", ["awarded_quote_id"])
    op.create_foreign_key(
        "fk_rfps_awarded_quote_id",
        "rfps",
        "rfp_vendor_quotes",
        ["awarded_quote_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_rfps_awarded_quote_id", "rfps", type_="foreignkey")
    op.drop_index("ix_rfps_awarded_quote_id", table_name="rfps")
    op.drop_column("rfps", "awarded_quote_id")
