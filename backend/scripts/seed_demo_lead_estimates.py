"""CLI wrapper for demo ``lead_estimates`` rows (see ``app.demo_lead_estimates``)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.demo_lead_estimates import upsert_demo_lead_estimates  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument(
        "--yes",
        action="store_true",
        help="Confirm writing to the database.",
    )
    p.add_argument(
        "--force",
        action="store_true",
        help="Deprecated: demo rows are always upserted by external_id. Kept for script compatibility.",
    )
    args = p.parse_args()
    if not args.yes:
        print("Refusing to run without --yes.", file=sys.stderr)
        return 2

    app = create_app()
    with app.app_context():
        n = upsert_demo_lead_estimates(db.session, force=args.force)
        if n:
            db.session.commit()
            print(f"Upserted {n} demo row(s) into lead_estimates.")
        else:
            print("No demo rows written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
