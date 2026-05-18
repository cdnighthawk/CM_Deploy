"""Preview or purge all fake users (pytest artifacts + HR @usis.local demos).

Runs purge_test_users.py then purge_hr_demo_users.py with the same flags.

Preview (dry run, default):
  cd backend
  python scripts/purge_all_fake_users.py

Production purge (Render Shell — backend service → Shell):
  cd backend
  python scripts/purge_all_fake_users.py
  python scripts/purge_all_fake_users.py --execute --i-know-this-is-production

Skip HR demo users (pytest junk only):
  python scripts/purge_all_fake_users.py --execute --skip-hr-demos --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete matched rows (default is dry-run preview only).",
    )
    parser.add_argument(
        "--i-know-this-is-production",
        action="store_true",
        help="Required with --execute when DATABASE_URL host is render.com / onrender.com.",
    )
    parser.add_argument(
        "--skip-hr-demos",
        action="store_true",
        help="Do not run purge_hr_demo_users.py (pytest/test junk only).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=15,
        metavar="N",
        help="Sample size passed to purge_test_users.py (default 15).",
    )
    args = parser.parse_args()

    shared = []
    if args.execute:
        shared.append("--execute")
    if args.i_know_this_is_production:
        shared.append("--i-know-this-is-production")

    steps: list[tuple[str, list[str]]] = [
        ("purge_test_users.py", ["--sample", str(max(0, args.sample))]),
    ]
    if not args.skip_hr_demos:
        steps.append(("purge_hr_demo_users.py", []))

    rc = 0
    for i, (script, extra) in enumerate(steps):
        if i:
            print()
        cmd = [sys.executable, str(_SCRIPTS / script), *extra, *shared]
        print(f">>> {' '.join(cmd)}")
        print()
        result = subprocess.run(cmd, cwd=_SCRIPTS.parent)
        if result.returncode:
            rc = result.returncode
            break

    return rc


if __name__ == "__main__":
    raise SystemExit(main())
