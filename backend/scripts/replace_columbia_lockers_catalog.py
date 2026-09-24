"""Replace the Columbia locker family from the repo seed CSV.

Keeps unique SKU labor when the unprefixed item matches. Does not truncate
other manufacturers.

Preview:
  python scripts/replace_columbia_lockers_catalog.py

Apply on Render Postgres:
  python scripts/replace_columbia_lockers_catalog.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_SCRIPTS))

from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402
from app.script_env import skip_startup_lead_bootstrap  # noqa: E402
from load_material_pricing import ensure_size_depth_column, replace_manufacturer_for_orgs  # noqa: E402
from material_csv_row import read_material_csv  # noqa: E402

CSV_PATH = _BACKEND / "data" / "catalog" / "columbia_lockers.csv"
MANUFACTURER = "Columbia"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--i-know-this-is-production", action="store_true")
    parser.add_argument("--csv", default=str(CSV_PATH))
    args = parser.parse_args()

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="replace_columbia_lockers_catalog.py",
    )
    if not args.execute:
        warn_if_production_preview()

    csv_path = Path(args.csv)
    payloads = read_material_csv(csv_path)
    if not payloads:
        raise SystemExit(f"no rows in {csv_path}")

    sized = sum(
        1
        for p in payloads
        if p.get("size_width_in") or p.get("size_depth_in") or p.get("size_height_in")
    )
    print(f"CSV rows: {len(payloads)} ({sized} with at least one dimension)")

    skip_startup_lead_bootstrap()
    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice
    from app.tenancy import include_all_orgs
    from sqlalchemy import func, select

    app = create_app()
    with app.app_context(), include_all_orgs():
        if args.execute and ensure_size_depth_column(db):
            print("Added material_pricing.size_depth_in")
        existing = db.session.scalars(
            select(MaterialPrice).where(func.lower(MaterialPrice.manufacturer) == MANUFACTURER.lower())
        ).all()
        print(f"Existing Columbia rows: {len(existing)}")
        if not args.execute:
            print("Dry run only. Pass --execute to replace.")
            return 0

        plans = replace_manufacturer_for_orgs(
            db,
            MaterialPrice,
            payloads,
            MANUFACTURER,
            delete_leftovers=True,
        )
        print(
            f"Replaced Columbia across {len(plans)} org(s): "
            f"{sum(p.updated_count for p in plans)} updated, "
            f"{sum(p.inserted_count for p in plans)} inserted, "
            f"{sum(p.deleted_count for p in plans)} deleted, "
            f"{sum(p.labor_copied for p in plans)} labor copied"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
