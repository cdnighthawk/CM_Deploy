"""Establish the shared job UID between corecon_transactions and lead_estimates.

Requires migration ``0008_active_project_external_id`` so ``active_project_external_id``
exists on ``corecon_transactions``.

Strategy
--------
1. For every distinct ``project_number`` found in ``corecon_transactions``,
   make sure a row exists in ``projects`` (keyed by ``projects.number``).
2. Back-fill ``corecon_transactions.project_id`` by joining on the number.
3. Refresh ``corecon_transactions.active_project_external_id`` (join key to
   ``lead_estimates.external_id`` for CORECON ``active project.csv`` rows).
4. Link CORECON ``lead_estimates`` to ``projects`` when ``number`` matches.
5. Report unmatched ``lead_estimates`` rows. BuildingConnected uses its own
   naming scheme (e.g. ``Wheeler Hangar PN76898``) that does not match
   Corecon's internal ``ProjectNumber`` (e.g. ``23090``); resolving those
   ties is a curation step, not an automatic one. The ``--match-leads``
   flag enables a simple, conservative name-based linker that only acts
   when the BC ``name`` exactly equals an existing ``projects.name``.

Usage (from the ``backend`` directory):

    python scripts\\link_jobs.py
    python scripts\\link_jobs.py --match-leads
    python scripts\\link_jobs.py --dry-run

The script is fully idempotent and safe to re-run after every CSV reload.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = THIS_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402


SYNC_PROJECTS_SQL = text(
    """
    WITH corecon_projects AS (
        SELECT
            project_number AS number,
            MIN(project_title) AS name
        FROM corecon_transactions
        WHERE project_number IS NOT NULL
          AND project_number <> ''
        GROUP BY project_number
    )
    INSERT INTO projects (
        id, number, name, status, project_type,
        prevailing_wage, dbe_required, created_at, updated_at
    )
    SELECT
        gen_random_uuid(),
        cp.number,
        COALESCE(NULLIF(TRIM(cp.name), ''), cp.number),
        'active'::project_status,
        'commercial'::project_type,
        false,
        false,
        NOW(),
        NOW()
    FROM corecon_projects cp
    ON CONFLICT (number) DO UPDATE
        SET name = COALESCE(NULLIF(TRIM(EXCLUDED.name), ''), projects.name),
            updated_at = NOW()
    RETURNING id, number;
    """
)

BACKFILL_CORECON_SQL = text(
    """
    UPDATE corecon_transactions ct
       SET project_id = p.id,
           updated_at = NOW()
      FROM projects p
     WHERE p.number = ct.project_number
       AND ct.project_id IS DISTINCT FROM p.id;
    """
)

SYNC_ACTIVE_PROJECT_EXTERNAL_ID_SQL = text(
    """
    UPDATE corecon_transactions
       SET active_project_external_id = CASE
             WHEN project_corecon_id IS NOT NULL
                 THEN 'corecon-project-' || project_corecon_id::text
             WHEN project_number IS NOT NULL AND trim(project_number) <> ''
                 THEN 'corecon-project-noid-' || trim(project_number)
             ELSE NULL
           END,
           updated_at = NOW();
    """
)

MATCH_CORECON_LEADS_BY_NUMBER_SQL = text(
    """
    UPDATE lead_estimates le
       SET project_id = p.id,
           updated_at = NOW()
      FROM projects p
     WHERE le.source = 'CORECON'
       AND le.project_id IS NULL
       AND le.number IS NOT NULL
       AND trim(le.number) <> ''
       AND p.number = trim(le.number);
    """
)

MATCH_LEADS_BY_NAME_SQL = text(
    """
    UPDATE lead_estimates le
       SET project_id = p.id,
           updated_at = NOW()
      FROM projects p
     WHERE le.project_id IS NULL
       AND le.name IS NOT NULL
       AND TRIM(le.name) <> ''
       AND p.name IS NOT NULL
       AND LOWER(TRIM(le.name)) = LOWER(TRIM(p.name));
    """
)

REPORT_SQL = text(
    """
    SELECT
        (SELECT COUNT(*) FROM projects)                                            AS total_projects,
        (SELECT COUNT(*) FROM corecon_transactions)                                AS total_corecon,
        (SELECT COUNT(*) FROM corecon_transactions WHERE project_id IS NOT NULL)   AS linked_corecon,
        (SELECT COUNT(*) FROM corecon_transactions WHERE project_id IS NULL)       AS unlinked_corecon,
        (SELECT COUNT(*) FROM corecon_transactions WHERE active_project_external_id IS NOT NULL)
            AS corecon_with_active_project_key,
        (SELECT COUNT(*) FROM lead_estimates)                                      AS total_leads,
        (SELECT COUNT(*) FROM lead_estimates WHERE project_id IS NOT NULL)         AS linked_leads,
        (SELECT COUNT(*) FROM lead_estimates WHERE project_id IS NULL)             AS unlinked_leads;
    """
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--match-leads",
        action="store_true",
        help="Also try to link lead_estimates by exact (case-insensitive) name match.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run inside a transaction and roll back at the end.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        try:
            print("Syncing projects from corecon_transactions ...")
            result = db.session.execute(SYNC_PROJECTS_SQL)
            touched = result.rowcount or 0
            print(f"   touched {touched} project row(s) (insert or update)")

            print("Back-filling corecon_transactions.project_id ...")
            result = db.session.execute(BACKFILL_CORECON_SQL)
            print(f"   updated {result.rowcount or 0} corecon row(s)")

            print("Syncing corecon_transactions.active_project_external_id ...")
            result = db.session.execute(SYNC_ACTIVE_PROJECT_EXTERNAL_ID_SQL)
            print(f"   refreshed {result.rowcount or 0} corecon row(s)")

            print("Linking CORECON lead_estimates by project number ...")
            result = db.session.execute(MATCH_CORECON_LEADS_BY_NUMBER_SQL)
            print(f"   linked {result.rowcount or 0} lead row(s)")

            if args.match_leads:
                print("Matching lead_estimates by exact name ...")
                result = db.session.execute(MATCH_LEADS_BY_NAME_SQL)
                print(f"   linked {result.rowcount or 0} lead row(s)")

            print("\nSummary:")
            row = db.session.execute(REPORT_SQL).mappings().one()
            for key, value in row.items():
                print(f"  {key:>18}: {value}")

            if args.dry_run:
                print("\n--dry-run set: rolling back.")
                db.session.rollback()
            else:
                db.session.commit()
                print("\nCommitted.")
        except Exception:
            db.session.rollback()
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
