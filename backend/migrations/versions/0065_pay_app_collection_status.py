"""Pay application collection statuses and paid_at.

Revision ID: 0065_pay_app_collection_status
Revises: 0065_project_contracts
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0065_pay_app_collection_status"
down_revision: Union[str, Sequence[str], None] = "0065_project_contracts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    for value in ("held", "rejected"):
        op.execute(sa.text(f"ALTER TYPE pay_application_status ADD VALUE IF NOT EXISTS '{value}'"))
    op.add_column("pay_applications", sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("pay_applications", "paid_at")
