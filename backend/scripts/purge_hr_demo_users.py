"""Remove Plan 19 HR seed/demo users only (never bulk-delete migrated staff).

Targets exactly:
  - hr.demo.employee@usis.local  (Jamie Rivera, migration 0021)
  - charles.dossett@usis.local     (Charles Dossett HR demo, migration 0022)
  - fixed UUIDs a1700000-… and b1700000-… if email was changed locally

HR child rows cascade via FK on users.id.

Preview (dry run, default):
  cd backend
  python scripts/purge_hr_demo_users.py

Apply deletes:
  python scripts/purge_hr_demo_users.py --execute

Equivalent SQL (preview first):
  SELECT id, email, first_name, last_name FROM users
  WHERE email IN ('hr.demo.employee@usis.local', 'charles.dossett@usis.local')
     OR id IN (
       'a1700000-0000-4000-8000-000000000001'::uuid,
       'b1700000-0000-4000-8000-000000000001'::uuid
     );

  -- After verifying row count (expect 0–2, never hundreds):
  DELETE FROM users
  WHERE email IN ('hr.demo.employee@usis.local', 'charles.dossett@usis.local')
     OR id IN (
       'a1700000-0000-4000-8000-000000000001'::uuid,
       'b1700000-0000-4000-8000-000000000001'::uuid
     );
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from sqlalchemy import or_, select  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402

DEMO_EMAILS = frozenset(
    {
        "hr.demo.employee@usis.local",
        "charles.dossett@usis.local",
    }
)
DEMO_IDS = frozenset(
    {
        uuid.UUID("a1700000-0000-4000-8000-000000000001"),
        uuid.UUID("b1700000-0000-4000-8000-000000000001"),
    }
)


def _demo_query():
    return select(User).where(
        or_(
            User.email.in_(sorted(DEMO_EMAILS)),
            User.id.in_(sorted(DEMO_IDS)),
        )
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete matching rows (default is dry-run preview only).",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        rows = db.session.scalars(_demo_query().order_by(User.email)).all()
        if not rows:
            print("No HR demo users matched (already removed or never seeded).")
            return 0

        print(f"Matched {len(rows)} user(s):")
        for u in rows:
            print(f"  {u.id}  {u.email}  {(u.first_name or '')} {(u.last_name or '')}".strip())

        if not args.execute:
            print("\nDry run — pass --execute to delete these rows only.")
            return 0

        for u in rows:
            db.session.delete(u)
        db.session.commit()
        print(f"Deleted {len(rows)} HR demo user(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
