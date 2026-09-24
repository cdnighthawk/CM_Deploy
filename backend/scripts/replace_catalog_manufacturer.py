"""Replace one manufacturer family from a repo seed CSV.

Keeps unique SKU labor. Does not truncate other manufacturers.
Does not touch Platinum Visual.

Preview:
  python scripts/replace_catalog_manufacturer.py --manufacturer APCO --csv data/catalog/apco_signs.csv

Apply on Render Postgres:
  python scripts/replace_catalog_manufacturer.py --manufacturer APCO --csv data/catalog/apco_signs.csv --execute --i-know-this-is-production
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
from load_material_pricing import (  # noqa: E402
    ensure_configurator_key_column,
    ensure_manufacturer_url_column,
    ensure_size_depth_column,
    replace_manufacturer_for_orgs,
)
from material_csv_row import read_material_csv  # noqa: E402

_BLOCKED = frozenset({"platinum visual", "platinum visual solutions"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manufacturer", required=True)
    parser.add_argument("--csv", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--i-know-this-is-production", action="store_true")
    args = parser.parse_args()

    manufacturer = args.manufacturer.strip()
    if manufacturer.lower() in _BLOCKED:
        raise SystemExit("Platinum Visual is owned by a different chat; refusing to replace it here.")

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="replace_catalog_manufacturer.py",
    )
    if not args.execute:
        warn_if_production_preview()

    csv_path = Path(args.csv)
    if not csv_path.is_absolute():
        csv_path = (_BACKEND / csv_path).resolve()
    payloads = read_material_csv(csv_path)
    extra_paths: list[Path] = []
    if manufacturer.lower() == "construction specialties":
        curtain = _BACKEND / "data" / "catalog" / "construction_specialties_cubicle_curtain.csv"
        if curtain.is_file() and csv_path.resolve() != curtain.resolve():
            extra_paths.append(curtain)
            payloads.extend(read_material_csv(curtain))
    if not payloads:
        raise SystemExit(f"no rows in {csv_path}")

    print(f"CSV rows: {len(payloads)} from {csv_path.name}" + (f" + {extra_paths[0].name}" if extra_paths else ""))

    skip_startup_lead_bootstrap()
    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice
    from app.tenancy import include_all_orgs
    from sqlalchemy import func, select

    app = create_app()
    with app.app_context(), include_all_orgs():
        if args.execute:
            if ensure_size_depth_column(db):
                print("Added material_pricing.size_depth_in")
            if ensure_manufacturer_url_column(db):
                print("Added material_pricing.manufacturer_url")
            if ensure_configurator_key_column(db):
                print("Added material_pricing.configurator_key")
        existing = db.session.scalars(
            select(MaterialPrice).where(func.lower(MaterialPrice.manufacturer) == manufacturer.lower())
        ).all()
        print(f"Existing {manufacturer} rows: {len(existing)}")
        if not args.execute:
            print("Dry run only. Pass --execute to replace.")
            return 0

        plans = replace_manufacturer_for_orgs(
            db,
            MaterialPrice,
            payloads,
            manufacturer,
            delete_leftovers=True,
        )
        print(
            f"Replaced {manufacturer} across {len(plans)} org(s): "
            f"{sum(p.updated_count for p in plans)} updated, "
            f"{sum(p.inserted_count for p in plans)} inserted, "
            f"{sum(p.deleted_count for p in plans)} deleted, "
            f"{sum(p.labor_copied for p in plans)} labor copied"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
