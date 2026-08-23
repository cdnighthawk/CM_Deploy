"""Bulk-load Bid Board opportunities into ``lead_estimates``.

Do **not** run a 40k historical pull through the live website. The Render web
service is a small dyno; this script is meant for Render Shell or a laptop
pointed at production Postgres.

Typical (Render Dashboard → usis-cm → Shell), after BuildingConnected OAuth
is connected on usiscm.com::

    python scripts/sync_buildingconnected_opportunities.py --full

Website sync after this only pulls the last 14 days of updates.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.api._integration_bc import _ensure_access_token, _pull_and_upsert  # noqa: E402
from app.extensions import db  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bc-bulk")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Bid Board opportunities into lead_estimates.")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Pull history since 2010 (use for the ~40k backfill). Default is last 14 days.",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Safety cap (100 rows/page). Default 500 with --full, else 50.",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        token = _ensure_access_token()
        loaded, skipped, errors = _pull_and_upsert(
            token,
            full=bool(args.full),
            max_pages=args.max_pages,
        )
        db.session.commit()

    log.info("Done: loaded=%s skipped=%s errors=%s", loaded, skipped, errors)
    print(f"Loaded {loaded} rows into lead_estimates (skipped {skipped}, errors {errors})")


if __name__ == "__main__":
    main()
