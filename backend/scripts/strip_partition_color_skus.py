"""Remove toilet-partition finish-color SKUs from material_pricing.

Keeps style/material rows (DesignerSeries HPL, DuraLineSeries CGL, ASI HDPE, …).
Deletes color chips attached to those styles (BOB-DL-*, BOB-DS-*, ASI-HDPE-9xxx, …).

Preview:
  python scripts/strip_partition_color_skus.py

Apply on Render Postgres:
  python scripts/strip_partition_color_skus.py --execute --i-know-this-is-production
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

from sqlalchemy import select  # noqa: E402

from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402
from app.script_env import skip_startup_lead_bootstrap  # noqa: E402
from material_csv_row import is_partition_color_sku  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--i-know-this-is-production", action="store_true")
    args = parser.parse_args()

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="strip_partition_color_skus.py",
    )
    if not args.execute:
        warn_if_production_preview()

    skip_startup_lead_bootstrap()
    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice
    from app.tenancy import include_all_orgs

    app = create_app()
    with app.app_context(), include_all_orgs():
        rows = db.session.scalars(select(MaterialPrice)).all()
        matches = [
            row
            for row in rows
            if is_partition_color_sku(
                item=row.item,
                category=row.category,
                description=row.description,
            )
        ]
        by_org: dict[object, list] = defaultdict(list)
        for row in matches:
            by_org[row.organization_id].append(row)

        print(f"Partition color SKUs: {len(matches)} across {len(by_org)} org(s)")
        for oid, org_rows in by_org.items():
            sample = [(r.item, (r.description or "")[:72]) for r in org_rows[:8]]
            print(f"  org {oid}: {len(org_rows)} rows; sample {sample}")

        series = [
            (row.manufacturer, row.item, (row.description or "")[:72])
            for row in rows
            if "toilet partition" in (row.category or "").casefold()
            and not is_partition_color_sku(
                item=row.item, category=row.category, description=row.description
            )
        ]
        print(f"Partition style rows remaining: {len(series)}")
        for line in series[:20]:
            print(f"  keep {line}")

        if not args.execute:
            print("Dry run only. Pass --execute to delete color SKUs.")
            return 0

        deleted = 0
        for row in matches:
            db.session.delete(row)
            deleted += 1
        db.session.commit()
        print(f"Deleted {deleted} partition color SKUs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
