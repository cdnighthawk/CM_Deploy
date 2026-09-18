"""Apply category labor hours / production rates from the reviewed labor sheet.

Preview:
  python scripts/apply_category_labor.py

Apply:
  python scripts/apply_category_labor.py --execute

Production:
  python scripts/apply_category_labor.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_SCRIPTS))

from sqlalchemy import select  # noqa: E402

from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402
from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

# Hours each — written only onto blank labor_per rows.
HOURS_EACH: dict[str, Decimal] = {
    "Glassboard": Decimal("1"),
    "Modular Drawer Cabinet": Decimal("1"),
    "Locker": Decimal("1.5"),
    "Fire Hose / Valve Cabinet": Decimal("1"),
    "Fire Extinguisher Cabinet": Decimal("1"),
    "Shelving": Decimal("1"),
    "Corner Guard": Decimal("0.75"),
    "Mirror / Shelf": Decimal("1"),
    "Bulletin Board": Decimal("1"),
    "Towel / Waste": Decimal("1"),
    "Whiteboard": Decimal("1"),
    "Enclosed Bulletin Board": Decimal("1"),
    "Toilet Partition": Decimal("5"),
    "Toilet Tissue Dispenser": Decimal("0.75"),
    "Locker Bench": Decimal("1"),
    "Hand Dryer": Decimal("1"),
    "Wall Covering": Decimal("1"),
    "Key Vault": Decimal("4"),
    "Fire Extinguisher": Decimal("0.5"),
    "Soap / Sanitizer Dispenser": Decimal("0.5"),
}

# Production rate — units per hour; catalog UOM is aligned to SF or LF.
# SF rates apply even when the manufacturer lists the SKU as EA (area products).
# LF rates never overwrite EA (those stay hours-per-each).
PRODUCTION: dict[str, tuple[Decimal, str]] = {
    "Handrail": (Decimal("8"), "LF"),
    "Crash Rail": (Decimal("8"), "LF"),
    "Rigid Sheet Wall Protection": (Decimal("30"), "SF"),
    "FRP Panel": (Decimal("30"), "SF"),
    "FRP Wall Panel": (Decimal("30"), "SF"),
    "Standard FRP Panel": (Decimal("30"), "SF"),
    "FRP Liner Panel": (Decimal("30"), "SF"),
    "Decorative FRP Panel": (Decimal("30"), "SF"),
    "Artizan Max FRP Panel": (Decimal("30"), "SF"),
    "Symmetrix FRP Tile Panel": (Decimal("30"), "SF"),
    "Decorative Wall Protection": (Decimal("20"), "SF"),
}


def _production_for(category: str) -> tuple[Decimal, str] | None:
    if category in PRODUCTION:
        return PRODUCTION[category]
    if "FRP" in category.upper():
        return (Decimal("30"), "SF")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--i-know-this-is-production", action="store_true")
    args = parser.parse_args()
    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="apply_category_labor.py",
    )
    if not args.execute:
        warn_if_production_preview()

    skip_startup_lead_bootstrap()
    from app import create_app
    from app.extensions import db
    from app.material_labor import sync_material_labor
    from app.models.material_pricing import MaterialPrice

    app = create_app()
    hours_n = 0
    rate_n = 0
    with app.app_context():
        rows = db.session.scalars(select(MaterialPrice)).all()
        for row in rows:
            cat = (row.category or "").strip()
            production = _production_for(cat)
            if production:
                from app.material_labor import RATE_EA, normalize_rate_unit

                rate, unit = production
                if unit == "LF" and normalize_rate_unit(row.unit_of_measure) == RATE_EA:
                    continue
                already = (
                    row.labor_units_per_hour == rate
                    and (row.labor_rate_unit or "") == unit
                    and (row.unit_of_measure or "") == unit
                )
                if already:
                    continue
                row.labor_units_per_hour = rate
                row.labor_rate_unit = unit
                sync_material_labor(row)
                rate_n += 1
                continue
            if cat in HOURS_EACH:
                if row.labor_per is not None:
                    continue
                row.labor_per = HOURS_EACH[cat]
                hours_n += 1
        if args.execute:
            db.session.commit()

    verb = "Updated" if args.execute else "Would update"
    print(f"{verb} {hours_n} hours-each rows and {rate_n} production-rate rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
