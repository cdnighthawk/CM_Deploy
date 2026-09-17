"""Normalize material catalog categories and parse sheet sizes.

Preview (dry run, default):
  cd backend
  python scripts/normalize_material_catalog.py

Apply:
  python scripts/normalize_material_catalog.py --execute

Production:
  python scripts/normalize_material_catalog.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_SCRIPTS))

from sqlalchemy import select  # noqa: E402

from _script_db_guard import require_safe_execute, warn_if_production_preview  # noqa: E402
from app.script_env import skip_startup_lead_bootstrap  # noqa: E402


def _should_parse_size(row) -> bool:
    from app.csi_spec import digits_from_csi

    if digits_from_csi(row.csi_spec_section) == "101100":
        return True
    cat = (row.category or "").lower()
    return any(
        key in cat
        for key in (
            "markerboard",
            "glassboard",
            "tackboard",
            "bulletin",
            "wall covering",
            "wall panel",
            "rigid sheet",
        )
    )


def _plan_row(row) -> dict[str, object] | None:
    from app.material_category import planned_category_update
    from app.material_size import parse_sheet_size, size_display

    changes: dict[str, object] = {}
    new_cat = planned_category_update(row)
    if new_cat is not None:
        changes["category"] = new_cat
    if _should_parse_size(row) and (row.size_width_in is None or row.size_height_in is None):
        w, h = parse_sheet_size(row.description, row.item)
        if w is not None and h is not None:
            if row.size_width_in is None:
                changes["size_width_in"] = w
            if row.size_height_in is None:
                changes["size_height_in"] = h
    if not changes:
        return None
    return {
        "id": row.id,
        "manufacturer": row.manufacturer,
        "item": row.item,
        "old_category": row.category,
        "size_display": size_display(
            changes.get("size_width_in", row.size_width_in),
            changes.get("size_height_in", row.size_height_in),
        ),
        "changes": changes,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write category and size updates (default is dry-run).",
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=25,
        metavar="N",
        help="How many sample rows to print (default 25).",
    )
    parser.add_argument(
        "--i-know-this-is-production",
        action="store_true",
        help="Required with --execute when DATABASE_URL host is render.com / onrender.com.",
    )
    args = parser.parse_args()

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="normalize_material_catalog.py",
    )
    if not args.execute:
        warn_if_production_preview()

    skip_startup_lead_bootstrap()
    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice

    app = create_app()
    total = 0
    with app.app_context():
        rows = db.session.scalars(select(MaterialPrice)).all()
        total = len(rows)
        plans = []
        cat_n = 0
        size_n = 0
        for row in rows:
            plan = _plan_row(row)
            if not plan:
                continue
            plans.append(plan)
            ch = plan["changes"]
            if "category" in ch:
                cat_n += 1
            if "size_width_in" in ch or "size_height_in" in ch:
                size_n += 1
            if args.execute:
                for key, value in ch.items():
                    setattr(row, key, value)
        if args.execute:
            db.session.commit()

    verb = "Updated" if args.execute else "Would update"
    print(f"{verb} {len(plans)} of {total} catalog rows ({cat_n} category, {size_n} size).")
    for plan in plans[: max(0, args.sample)]:
        ch = plan["changes"]
        bits = []
        if "category" in ch:
            bits.append(f"{plan['old_category']!r} -> {ch['category']!r}")
        if plan.get("size_display") and ("size_width_in" in ch or "size_height_in" in ch):
            bits.append(f"size {plan['size_display']}")
        print(f"  {plan['manufacturer']} {plan['item']}: " + "; ".join(bits))
    if len(plans) > args.sample:
        print(f"  … {len(plans) - args.sample} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
