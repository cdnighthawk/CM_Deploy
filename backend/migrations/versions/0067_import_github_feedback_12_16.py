"""Import GitHub hub reports #12–#16 into the internal issues tracker.

Revision ID: 0067_import_github_feedback_12_16
Revises: 0066_schedule_item_assignee
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0067_import_github_feedback_12_16"
down_revision: Union[str, Sequence[str], None] = "0066_schedule_item_assignee"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy.orm import Session

    from app.services.github_issue_import import import_bundled_github_issues

    session = Session(bind=op.get_bind())
    import_bundled_github_issues(session, commit=False)


def downgrade() -> None:
    from sqlalchemy import text

    op.get_bind().execute(
        text(
            """
            DELETE FROM tracker_issue_events
            WHERE issue_id IN (
                SELECT id FROM tracker_issues
                WHERE source_type = 'feedback'
                  AND linked_change_order_id IN (
                    'github:12', 'github:13', 'github:14', 'github:15', 'github:16'
                  )
            )
            """
        )
    )
    op.get_bind().execute(
        text(
            """
            DELETE FROM tracker_issues
            WHERE source_type = 'feedback'
              AND linked_change_order_id IN (
                'github:12', 'github:13', 'github:14', 'github:15', 'github:16'
              )
            """
        )
    )
