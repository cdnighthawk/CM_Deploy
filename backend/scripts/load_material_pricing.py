"""Load material_pricing rows from the Bobrick / multi-vendor material CSV."""
from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

_DEFAULT_CSV = str(database_files_dir() / "BOBRICK MATERIAL PRICING.CSV")


def _blank_to_none(s: str | None) -> str | None:
    if s is None:
        return None
    stripped = s.strip()
    return None if stripped == "" else stripped


def _parse_decimal(raw: str | None) -> Decimal | None:
    s = (raw or "").strip()
    if s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"invalid decimal: {raw!r}") from exc


def _row_to_payload(row: dict[str, str]) -> dict[str, object]:
    manufacturer = _blank_to_none(row.get("Manufacturer"))
    item = _blank_to_none(row.get("Item"))
    if not manufacturer or not item:
        raise ValueError("Manufacturer and Item are required (got blank values)")

    category = _blank_to_none(row.get("Category"))
    description = _blank_to_none(row.get("Description"))
    mounting_type = _blank_to_none(row.get("Mounting Type"))
    cost = _parse_decimal(row.get("Cost"))
    labor_per = _parse_decimal(row.get("Labor Per"))

    return {
        "manufacturer": manufacturer,
        "item": item,
        "category": category,
        "description": description,
        "mounting_type": mounting_type,
        "cost": cost,
        "labor_per": labor_per,
        "currency": "USD",
        "unit_of_measure": "EA",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Load material_pricing from CSV.")
    parser.add_argument("--csv", default=_DEFAULT_CSV, help="Path to the source CSV file.")
    parser.add_argument(
        "--truncate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Truncate table before load (default: true). Use --no-truncate to upsert.",
    )
    args = parser.parse_args()

    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.sql import func

    from app.script_env import skip_startup_lead_bootstrap

    skip_startup_lead_bootstrap()

    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice

    app = create_app()
    csv_path = Path(args.csv)
    if not csv_path.is_file():
        raise SystemExit(f"CSV not found: {csv_path}")

    payloads: list[dict[str, object]] = []
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        expected = {
            "Manufacturer",
            "Item",
            "Category",
            "Cost",
            "Description",
            "Mounting Type",
            "Labor Per",
        }
        if reader.fieldnames is None:
            raise SystemExit("CSV has no header row")
        missing = expected - set(reader.fieldnames)
        if missing:
            raise SystemExit(f"CSV missing columns: {sorted(missing)}")

        for row in reader:
            payloads.append(_row_to_payload(row))

    with app.app_context():
        if args.truncate:
            db.session.execute(text("TRUNCATE material_pricing RESTART IDENTITY"))
            db.session.commit()

        if args.truncate:
            db.session.bulk_insert_mappings(MaterialPrice, payloads)
            db.session.commit()
        else:
            table = MaterialPrice.__table__
            for p in payloads:
                ins = pg_insert(table).values(**p)
                stmt = ins.on_conflict_do_update(
                    index_elements=["manufacturer", "item"],
                    set_={
                        "category": ins.excluded.category,
                        "description": ins.excluded.description,
                        "mounting_type": ins.excluded.mounting_type,
                        "cost": ins.excluded.cost,
                        "labor_per": ins.excluded.labor_per,
                        "currency": ins.excluded.currency,
                        "unit_of_measure": ins.excluded.unit_of_measure,
                        "updated_at": func.now(),
                    },
                )
                db.session.execute(stmt)
            db.session.commit()

    print(f"Loaded {len(payloads)} rows into material_pricing")


if __name__ == "__main__":
    main()
