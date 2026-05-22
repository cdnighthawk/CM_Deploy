"""Deprecated: Plan 19 HR demo seed removed by migration 0050.

Do not re-seed Jamie Rivera / Charles Dossett demo users in production.
Use User admin for real staff, or ``python scripts/purge_hr_demo_users.py --execute``
if legacy demo rows remain.
"""
from __future__ import annotations

import sys


def main() -> int:
    print(
        "seed_hr_employees.py is deprecated. Demo HR users were removed in migration 0050.\n"
        "Add real employees via User admin. To purge any leftover demo rows:\n"
        "  python scripts/purge_hr_demo_users.py --execute --i-know-this-is-production"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
