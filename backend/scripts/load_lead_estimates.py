"""Load BuildingConnected lead_estimates from CSV (batched Core inserts / upserts)."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.lead_estimate_csv_load import load_lead_estimates_csv  # noqa: E402
from app.models.lead_estimate import LeadEstimate  # noqa: E402, F401

def _default_csv_path() -> str:
    env = (os.environ.get("BC_PROJECTS_CSV") or "").strip()
    if env and Path(env).is_file():
        return env
    d = database_files_dir()
    matches = sorted(d.glob("bc_projects*.csv"))
    if matches:
        return str(matches[-1])
    return str(d / "bc_projects_20260419_161452.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load lead_estimates from BuildingConnected CSV.")
    parser.add_argument(
        "--csv",
        default=_default_csv_path(),
        help="Path to bc_projects CSV export (defaults to BC_PROJECTS_CSV if set, else bundled fallback path)",
    )
    parser.add_argument("--batch-size", type=int, default=1000, help="Rows per insert / commit")
    parser.add_argument(
        "--mode",
        choices=("upsert", "truncate"),
        default="upsert",
        help="truncate: TRUNCATE then insert; upsert: ON CONFLICT DO UPDATE on external_id",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        loaded, skipped, errors = load_lead_estimates_csv(
            db.session, args.csv, mode=args.mode, batch_size=args.batch_size
        )

    print(f"Loaded {loaded} rows into lead_estimates (skipped {skipped}, errors {errors})")


if __name__ == "__main__":
    main()
