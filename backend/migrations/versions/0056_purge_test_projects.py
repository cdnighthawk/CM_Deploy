"""Purge pytest/API-test project rows left in the live database.

Matches ``app.projects.test_artifacts.is_test_artifact_project``.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

revision: str = "0056_purge_test_projects"
down_revision: Union[str, Sequence[str], None] = "0055_commitment_sage_po"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.get_bind().execute(
        text(
            """
            DELETE FROM projects
            WHERE number ~* '^num-[0-9a-f]{10}$'
               OR LOWER(TRIM(name)) IN (
                 'admin ann',
                 'bic test',
                 'rollup api test project',
                 'uniquesearchwidgetxyz',
                 'scoped sync',
                 'scope test job',
                 'job a',
                 'job b',
                 'assigned',
                 'other',
                 'x1',
                 'x2',
                 'px',
                 'py',
                 'pz'
               )
               OR name ~* '^detail-[0-9a-f]{10}$'
               OR name ~* '^num-[0-9a-f]{10}$'
               OR name ~* '^att-[0-9a-f]{8}$'
               OR name ~* '^docproj-[0-9a-f]{8}$'
               OR name ~* '^schedproj-[0-9a-f]{8}$'
               OR name ~* '^payproj-[0-9a-f]{8}$'
               OR name ~* '^sovproj-[0-9a-f]{8}$'
               OR name ~* '^specf-[0-9a-f]{8}$'
               OR name ~* '^proc-[0-9a-f]{8}$'
               OR name ~* '^procrfp-[0-9a-f]{8}$'
               OR name ~* '^rfi-p-[0-9a-f]{6}$'
               OR name ~* '^p[1-5]-[0-9a-f]{6}$'
               OR name ~* '^t-[0-9a-f]{10}$'
               OR name ~* '^draw(-|1-|del-)[0-9a-f]{8}$'
            """
        )
    )


def downgrade() -> None:
    # Test fixtures should not be restored.
    pass
