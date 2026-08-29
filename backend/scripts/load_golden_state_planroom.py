"""Load AGC San Diego weekly listing CSV into golden_state_planroom_leads."""
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
from app.golden_state_planroom_csv import load_agcs_weekly_csv  # noqa: E402


def _default_csv_path() -> str:
    env = (os.environ.get("AGCS_PROJECTS_CSV") or "").strip()
    if env and Path(env).is_file():
        return env
    downloads = Path.home() / "Downloads" / "AGCS_CAProjects.csv"
    if downloads.is_file():
        return str(downloads)
    d = database_files_dir()
    matches = sorted(d.glob("AGCS_*.csv"))
    if matches:
        return str(matches[-1])
    return str(d / "AGCS_CAProjects.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load Golden State / AGC weekly planroom CSV.")
    parser.add_argument("--csv", default=_default_csv_path(), help="Path to AGCS_CAProjects.csv")
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        loaded, skipped, listing_week = load_agcs_weekly_csv(db.session, args.csv)

    week = listing_week.isoformat() if listing_week else "unknown"
    print(f"Loaded {loaded} Golden State planroom rows (skipped {skipped}, listing week {week})")


if __name__ == "__main__":
    main()
