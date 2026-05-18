"""Remove pytest / API-test user rows from production (safe allowlist).

See ``app.users.test_artifacts`` for matching rules.

Preview (dry run, default):
  cd backend
  python scripts/purge_test_users.py

Apply deletes (Render Shell — open backend service → Shell):
  cd backend
  python scripts/purge_test_users.py --execute --i-know-this-is-production

Purge pytest junk + HR demos in one go:
  python scripts/purge_all_fake_users.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_SCRIPTS))

from sqlalchemy import select  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402
from app.users.test_artifacts import is_test_artifact_email  # noqa: E402
from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402


def _all_users_ordered():
    return db.session.scalars(select(User).order_by(User.email)).all()


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
        default=15,
        metavar="N",
        help="How many sample emails to print in dry-run (default 15).",
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
        script_name="purge_test_users.py",
    )
    if not args.execute:
        warn_if_production_preview()

    app = create_app()
    with app.app_context():
        rows = [u for u in _all_users_ordered() if is_test_artifact_email(u.email)]
        if not rows:
            print("No pytest/test artifact users matched.")
            return 0

        print(f"Matched {len(rows)} test artifact user(s).")
        sample_n = max(0, args.sample)
        if sample_n:
            print(f"Sample (up to {sample_n}):")
            for u in rows[:sample_n]:
                print(f"  {u.id}  {u.email}")
            if len(rows) > sample_n:
                print(f"  … and {len(rows) - sample_n} more")

        if not args.execute:
            print("\nDry run — pass --execute to delete these rows only.")
            print("HR demo users (@usis.local) are never matched here; use purge_hr_demo_users.py if needed.")
            return 0

        for u in rows:
            db.session.delete(u)
        db.session.commit()
        print(f"Deleted {len(rows)} test artifact user(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
