"""Import existing GitHub hub reports into the internal issues tracker.

Revision ID: 0059_import_github_feedback
Revises: 0058_tracker_issues
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0059_import_github_feedback"
down_revision: Union[str, Sequence[str], None] = "0058_tracker_issues"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from app.services.github_issue_import import import_bundled_github_issues

    import_bundled_github_issues()


def downgrade() -> None:
    op.get_bind().execute(
        text(
            """
            DELETE FROM tracker_issue_events
            WHERE issue_id IN (
                SELECT id FROM tracker_issues
                WHERE source_type = 'feedback' AND linked_change_order_id LIKE 'github:%'
            )
            """
        )
    )
    op.get_bind().execute(
        text(
            """
            DELETE FROM tracker_issues
            WHERE source_type = 'feedback' AND linked_change_order_id LIKE 'github:%'
            """
        )
    )
