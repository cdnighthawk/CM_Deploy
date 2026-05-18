"""Remove pytest / API-test user rows from production (safe allowlist).

Matches users whose email is a known automated-test artifact:
  - ends with @t.com or @example.com (pytest fixtures), or
  - local-part starts with a known test prefix (see TEST_LOCAL_PREFIXES)

Never deletes:
  - charles@gousis.com, any @godocon.com / @gousis.com address
  - any @usis.local address (HR demos — use purge_hr_demo_users.py or purge_all_fake_users.py)
  - BOOTSTRAP_ADMIN_EMAIL (if set in the environment)

Production was polluted when pytest ran against the live DATABASE_URL. Use a
separate test database for CI/local pytest (TEST_DATABASE_URL or ephemeral DB).

Preview (dry run, default):
  cd backend
  python scripts/purge_test_users.py

Apply deletes (Render Shell — open backend service → Shell):
  cd backend
  python scripts/purge_test_users.py --execute --i-know-this-is-production

Purge pytest junk + HR demos in one go:
  python scripts/purge_all_fake_users.py --execute --i-know-this-is-production

Optional: show more sample emails in dry-run:
  python scripts/purge_test_users.py --sample 30
"""
from __future__ import annotations

import argparse
import os
import re
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
from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402

ALLOWLIST_EMAILS = frozenset({"charles@gousis.com"})

PROTECTED_DOMAIN_SUFFIXES = (
    "@godocon.com",
    "@gousis.com",
    "@usis.local",
)

# Local-parts from backend/tests/* (prefix + uuid hex + @t.com or @example.com).
TEST_LOCAL_PREFIXES = (
    "adm_",
    "adm2_",
    "att_",
    "badnext_",
    "bic_owner_",
    "bic_other_",
    "cmp_",
    "d_",
    "doc_u_",
    "em_",
    "hire_",
    "hradm_",
    "hrms_",
    "login_",
    "lo_",
    "mgr_",
    "mobile_",
    "ms_ok_",
    "newu_",
    "next_",
    "out_",
    "pay_u_",
    "pbi_u_",
    "playbook_tester_",
    "priv_",
    "proc_rfp_",
    "proc_u_",
    "prof_",
    "sched_u_",
    "sov_u_",
    "std_",
    "sub_",
    "u_",
)

_TEST_PREFIX_RE = re.compile(
    r"^(" + "|".join(re.escape(p) for p in TEST_LOCAL_PREFIXES) + r")",
    re.IGNORECASE,
)


def _bootstrap_admin_email() -> str | None:
    raw = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    return raw or None


def is_test_artifact_email(email: str | None) -> bool:
    """True only when email clearly matches pytest/API test patterns."""
    if not email or not email.strip():
        return False
    e = email.strip().lower()
    if e in ALLOWLIST_EMAILS:
        return False
    bootstrap = _bootstrap_admin_email()
    if bootstrap and e == bootstrap:
        return False
    for suffix in PROTECTED_DOMAIN_SUFFIXES:
        if e.endswith(suffix):
            return False
    if e.endswith("@t.com") or e.endswith("@example.com"):
        return True
    local = e.split("@", 1)[0]
    return bool(_TEST_PREFIX_RE.match(local))


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
