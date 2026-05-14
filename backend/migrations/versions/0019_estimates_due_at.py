"""Add optional due date on formal estimate headers."""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_estimates_due_at"
down_revision: Union[str, Sequence[str], None] = "0018_rfp_core"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("estimates", sa.Column("due_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_estimates_due_at", "estimates", ["due_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_estimates_due_at", table_name="estimates")
    op.drop_column("estimates", "due_at")
