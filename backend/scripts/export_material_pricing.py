"""Export material_pricing rows to CSV for catalog review.

Usage (from backend/, with DATABASE_URL set):

    python scripts/export_material_pricing.py
    python scripts/export_material_pricing.py --out data/catalog/exports/items.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))


def _iso(value) -> str:
    if value is None:
        return ""
    if getattr(value, "tzinfo", None) is None:
        return value.isoformat()
    return value.astimezone(timezone.utc).isoformat()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export material_pricing catalog rows.")
    parser.add_argument(
        "--out",
        default="",
        help="Item CSV path. Default: data/catalog/exports/material_pricing_items_<date>.csv",
    )
    parser.add_argument(
        "--summary-out",
        default="",
        help="CSI/category count CSV path. Default: next to --out with _by_csi_category suffix.",
    )
    args = parser.parse_args()

    from app.script_env import skip_startup_lead_bootstrap

    skip_startup_lead_bootstrap()

    from app import create_app
    from app.csi_catalog import DIVISION_NAMES, title_for_code
    from app.csi_spec import digits_from_csi, format_csi_display
    from app.extensions import db
    from app.material_labor import labor_production_display
    from app.material_size import sheet_area_sf, size_display
    from app.models.material_pricing import MaterialPrice
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload

    stamp = datetime.now().strftime("%Y-%m-%d")
    export_dir = _BACKEND_ROOT / "data" / "catalog" / "exports"
    out_path = Path(args.out) if args.out else export_dir / f"material_pricing_items_{stamp}.csv"
    if not out_path.is_absolute():
        out_path = (_BACKEND_ROOT / out_path).resolve()
    if args.summary_out:
        summary_path = Path(args.summary_out)
        if not summary_path.is_absolute():
            summary_path = (_BACKEND_ROOT / summary_path).resolve()
    else:
        summary_path = out_path.with_name(out_path.stem + "_by_csi_category.csv")

    app = create_app()
    with app.app_context():
        uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        if "CHANGE_ME_APP_PASSWORD" in uri:
            raise SystemExit(
                "Set DATABASE_URL to the Render usis-cm-db External URL before exporting."
            )
        rows = db.session.scalars(
            select(MaterialPrice)
            .options(joinedload(MaterialPrice.supplier_company))
            .order_by(
                MaterialPrice.csi_spec_section.asc().nulls_last(),
                MaterialPrice.manufacturer.asc(),
                MaterialPrice.category.asc().nulls_last(),
                MaterialPrice.item.asc(),
            )
        ).all()

        out_path.parent.mkdir(parents=True, exist_ok=True)
        item_fields = [
            "id",
            "manufacturer",
            "manufacturer_url",
            "item",
            "category",
            "csi_spec_section",
            "csi_display",
            "csi_title",
            "csi_division",
            "csi_division_name",
            "description",
            "mounting_type",
            "size_width_in",
            "size_height_in",
            "size_depth_in",
            "size_display",
            "sheet_area_sf",
            "cost",
            "labor_per",
            "labor_units_per_hour",
            "labor_rate_unit",
            "labor_production",
            "currency",
            "unit_of_measure",
            "supplier_company_id",
            "supplier_name",
            "supplier_email",
            "created_at",
            "updated_at",
        ]
        counts: Counter[tuple[str, str, str, str]] = Counter()
        mfr_counts: Counter[str] = Counter()
        csi_counts: Counter[str] = Counter()
        missing_csi = 0
        missing_category = 0

        with out_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=item_fields, extrasaction="ignore")
            writer.writeheader()
            for m in rows:
                digits = digits_from_csi(m.csi_spec_section)
                div = digits[:2] if digits else ""
                csi_display = format_csi_display(m.csi_spec_section) or (m.csi_spec_section or "")
                csi_title = title_for_code(m.csi_spec_section) or ""
                category = (m.category or "").strip()
                if not digits:
                    missing_csi += 1
                if not category:
                    missing_category += 1
                mfr = (m.manufacturer or "").strip()
                mfr_counts[mfr or "(blank)"] += 1
                csi_counts[csi_display or "(blank)"] += 1
                counts[(csi_display or "(blank)", csi_title or "(none)", mfr or "(blank)", category or "(blank)")] += 1
                writer.writerow(
                    {
                        "id": str(m.id),
                        "manufacturer": m.manufacturer or "",
                        "manufacturer_url": m.manufacturer_url or "",
                        "item": m.item or "",
                        "category": category,
                        "csi_spec_section": m.csi_spec_section or "",
                        "csi_display": csi_display,
                        "csi_title": csi_title,
                        "csi_division": div,
                        "csi_division_name": DIVISION_NAMES.get(div, "") if div else "",
                        "description": m.description or "",
                        "mounting_type": m.mounting_type or "",
                        "size_width_in": "" if m.size_width_in is None else str(m.size_width_in),
                        "size_height_in": "" if m.size_height_in is None else str(m.size_height_in),
                        "size_depth_in": "" if m.size_depth_in is None else str(m.size_depth_in),
                        "size_display": size_display(m.size_width_in, m.size_height_in, m.size_depth_in) or "",
                        "sheet_area_sf": ""
                        if sheet_area_sf(m.size_width_in, m.size_height_in) is None
                        else str(sheet_area_sf(m.size_width_in, m.size_height_in)),
                        "cost": "" if m.cost is None else str(m.cost),
                        "labor_per": "" if m.labor_per is None else str(m.labor_per),
                        "labor_units_per_hour": ""
                        if m.labor_units_per_hour is None
                        else str(m.labor_units_per_hour),
                        "labor_rate_unit": m.labor_rate_unit or "",
                        "labor_production": labor_production_display(
                            m.labor_units_per_hour, m.labor_rate_unit
                        )
                        or "",
                        "currency": m.currency or "",
                        "unit_of_measure": m.unit_of_measure or "",
                        "supplier_company_id": str(m.supplier_company_id) if m.supplier_company_id else "",
                        "supplier_name": (m.supplier_company.name if m.supplier_company else ""),
                        "supplier_email": (
                            (m.supplier_company.email or "") if m.supplier_company else ""
                        ),
                        "created_at": _iso(getattr(m, "created_at", None)),
                        "updated_at": _iso(getattr(m, "updated_at", None)),
                    }
                )

        with summary_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=["csi_display", "csi_title", "manufacturer", "category", "item_count"],
            )
            writer.writeheader()
            for (csi_display, csi_title, mfr, category), n in sorted(
                counts.items(), key=lambda kv: (-kv[1], kv[0][0], kv[0][2], kv[0][3])
            ):
                writer.writerow(
                    {
                        "csi_display": csi_display,
                        "csi_title": csi_title,
                        "manufacturer": mfr,
                        "category": category,
                        "item_count": n,
                    }
                )

    print(f"Wrote {len(rows)} items -> {out_path}")
    print(f"Wrote {len(counts)} CSI/manufacturer/category groups -> {summary_path}")
    print(f"Manufacturers: {len(mfr_counts)}")
    print(f"CSI sections: {len([k for k in csi_counts if k != '(blank)'])}")
    print(f"Missing CSI: {missing_csi}")
    print(f"Missing category: {missing_category}")
    print("Top CSI sections:")
    for key, n in csi_counts.most_common(15):
        print(f"  {n:5d}  {key}")
    print("Top manufacturers:")
    for key, n in mfr_counts.most_common(15):
        print(f"  {n:5d}  {key}")


if __name__ == "__main__":
    main()
