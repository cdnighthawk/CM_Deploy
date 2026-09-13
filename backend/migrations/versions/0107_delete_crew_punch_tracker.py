"""Remove crew punch cards from the website Issues board.

Revision ID: 0107_drop_crew_punch
Revises: 0106_user_office
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0107_drop_crew_punch"
down_revision: Union[str, Sequence[str], None] = "0106_user_office"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DELETE FROM tracker_issues WHERE source_type = 'crew_punch'")


def downgrade() -> None:
    pass
