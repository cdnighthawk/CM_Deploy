"""Replace Accurate Partitions catalog garbage with brand × height SKUs.

Preview:
  python scripts/replace_accurate_partitions_catalog.py

Apply on Render Postgres:
  python scripts/replace_accurate_partitions_catalog.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_SCRIPTS))

from sqlalchemy import func, select  # noqa: E402

from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402
from app.script_env import skip_startup_lead_bootstrap  # noqa: E402
from material_csv_row import read_material_csv  # noqa: E402

CSV_PATH = _BACKEND / "data" / "catalog" / "accurate_partitions.csv"
MANUFACTURER = "Accurate Partitions"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--i-know-this-is-production", action="store_true")
    parser.add_argument("--csv", default=str(CSV_PATH))
    args = parser.parse_args()

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="replace_accurate_partitions_catalog.py",
    )
    if not args.execute:
        warn_if_production_preview()

    csv_path = Path(args.csv)
    payloads = read_material_csv(csv_path)
    if not payloads:
        raise SystemExit(f"no rows in {csv_path}")

    skip_startup_lead_bootstrap()
    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice
    from app.tenancy import include_all_orgs

    app = create_app()
    with app.app_context(), include_all_orgs():
        existing = db.session.scalars(
            select(MaterialPrice).where(func.lower(MaterialPrice.manufacturer) == MANUFACTURER.lower())
        ).all()
        by_org: dict[object, list] = defaultdict(list)
        for row in existing:
            by_org[row.organization_id].append(row)

        print(f"CSV rows: {len(payloads)}")
        print(f"Existing Accurate Partitions rows: {len(existing)} across {len(by_org)} org(s)")
        for oid, rows in by_org.items():
            sample = (rows[0].description or "")[:80]
            print(f"  org {oid}: {len(rows)} rows; sample description: {sample!r}")

        if not args.execute:
            print("Dry run only. Pass --execute to replace.")
            return 0

        orgs = list(by_org) or []
        if not orgs:
            from app.tenancy import default_organization_id

            oid = default_organization_id()
            if oid is None:
                raise SystemExit("no Accurate Partitions rows and no default organization")
            orgs = [oid]
            print(f"No existing rows; inserting into default org {oid}")

        deleted = 0
        inserted = 0
        for oid in orgs:
            for row in by_org.get(oid, []):
                db.session.delete(row)
                deleted += 1
            db.session.flush()
            for payload in payloads:
                db.session.add(MaterialPrice(organization_id=oid, **payload))
                inserted += 1
        db.session.commit()
        print(f"Deleted {deleted} garbage/old rows; inserted {inserted} brand×height rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
