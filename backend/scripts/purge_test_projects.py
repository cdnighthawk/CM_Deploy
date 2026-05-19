"""Remove pytest / API-test project rows (safe name/number patterns only).

Preview (dry run, default):
  cd backend
  python scripts/purge_test_projects.py

Apply deletes (local or Render Shell):
  python scripts/purge_test_projects.py --execute

Production (Render Shell):
  python scripts/purge_test_projects.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_SCRIPTS))

from types import SimpleNamespace

from sqlalchemy import text  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.projects.test_artifacts import is_test_artifact_project  # noqa: E402
from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402


def _load_projects() -> list[SimpleNamespace]:
    """Load id/name/number/status without requiring every ORM column to exist in DB."""
    rows = db.session.execute(
        text(
            "SELECT id, name, number, status::text AS status FROM projects ORDER BY name, number"
        )
    ).fetchall()
    return [
        SimpleNamespace(id=r.id, name=r.name, number=r.number, status=r.status) for r in rows
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete matched rows (default is dry-run preview only).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=20,
        metavar="N",
        help="How many sample rows to print in dry-run (default 20).",
    )
    parser.add_argument(
        "--i-know-this-is-production",
        action="store_true",
        help="Required with --execute when DATABASE_URL host is render.com / onrender.com.",
    )
    args = parser.parse_args()

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="purge_test_projects.py",
    )
    if not args.execute:
        warn_if_production_preview()

    app = create_app()
    with app.app_context():
        all_projects = _load_projects()
        matched = [p for p in all_projects if is_test_artifact_project(p)]
        kept = len(all_projects) - len(matched)

        if not matched:
            print(f"No test artifact projects matched ({len(all_projects)} total projects).")
            return 0

        print(f"Matched {len(matched)} test artifact project(s) of {len(all_projects)} total.")
        print(f"Would keep {kept} project(s).")
        sample_n = max(0, args.sample)
        if sample_n:
            print(f"\nSample (up to {sample_n}):")
            for p in matched[:sample_n]:
                num = p.number or "—"
                print(f"  {p.id}  {num!s:22}  {p.name!s}  ({p.status})")
            if len(matched) > sample_n:
                print(f"  … and {len(matched) - sample_n} more")

        if not args.execute:
            print("\nDry run — pass --execute to delete these rows only.")
            return 0

        ids = [p.id for p in matched]
        db.session.execute(
            text("DELETE FROM projects WHERE id = ANY(CAST(:ids AS uuid[]))"),
            {"ids": ids},
        )
        db.session.commit()
        print(f"\nDeleted {len(matched)} test artifact project(s). {kept} remaining.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
