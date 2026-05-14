"""Load CDTFA California sales/use tax rates from CSV into ``sales_tax_rates``."""
from __future__ import annotations

import argparse
import csv
import logging
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

# Allow ``from app import create_app`` when run as ``python scripts/load_sales_tax_rates.py``.
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap

skip_startup_lead_bootstrap()

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app import create_app
from app.extensions import db
from app.models.sales_tax_rate import SalesTaxRate

DEFAULT_CSV = str(database_files_dir() / "cdtfa_sales_use_tax_rates_raw.csv.csv")

_LOG = logging.getLogger(__name__)


def open_cdtfa_dict_reader(path: Path):
    """Skip the first two junk lines; line 3 is the real CSV header."""
    f = path.open(newline="", encoding="utf-8")
    plain = csv.reader(f)
    try:
        next(plain)
        next(plain)
    except StopIteration:
        f.close()
        raise ValueError(f"CSV at {path} has fewer than 3 lines (expected header on line 3).") from None
    return f, csv.DictReader(f)


def _blank_to_none(s: str | None) -> str | None:
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def parse_row(row: dict[str, str | None]) -> dict | None:
    """Return a dict of DB columns or None if the row should be skipped (invalid)."""
    loc_raw = row.get("Location")
    location = (loc_raw or "").strip()
    if not location:
        return None

    rate_raw = (row.get("Rate") or "").strip()
    if not rate_raw:
        return None
    try:
        rate = Decimal(rate_raw)
    except InvalidOperation:
        return None

    type_raw = _blank_to_none(row.get("Type"))
    rate_type = type_raw if type_raw is not None else "Unknown"

    return {
        "state": "CA",
        "location": location,
        "rate": rate,
        "county": _blank_to_none(row.get("County")),
        "type": rate_type,
        "notes": _blank_to_none(row.get("Notes")),
        "effective_date": None,
        "source": "CDTFA",
    }


def load_rows(csv_path: Path, truncate: bool) -> tuple[int, int]:
    """Insert rows; returns (loaded_count, skipped_count)."""
    loaded = 0
    skipped = 0

    f, dict_reader = open_cdtfa_dict_reader(csv_path)
    try:
        rows: list[dict] = []
        for raw in dict_reader:
            if not raw:
                continue
            parsed = parse_row(raw)
            if parsed is None:
                skipped += 1
                _LOG.warning("Skipping row (blank location or invalid rate): %r", raw)
                continue
            rows.append(parsed)
    finally:
        f.close()

    table = SalesTaxRate.__table__

    with db.session.begin():
        if truncate:
            db.session.execute(text("TRUNCATE sales_tax_rates RESTART IDENTITY"))
            db.session.bulk_insert_mappings(SalesTaxRate, rows)
            loaded = len(rows)
        else:
            for data in rows:
                insert_stmt = pg_insert(table).values(**data)
                upsert = insert_stmt.on_conflict_do_update(
                    index_elements=["state", "location", "type"],
                    set_={
                        "rate": insert_stmt.excluded.rate,
                        "county": insert_stmt.excluded.county,
                        "notes": insert_stmt.excluded.notes,
                        "effective_date": insert_stmt.excluded.effective_date,
                        "source": insert_stmt.excluded.source,
                        "updated_at": func.now(),
                    },
                )
                db.session.execute(upsert)
            loaded = len(rows)

    return loaded, skipped


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(DEFAULT_CSV),
        help=f"Path to CDTFA CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument(
        "--truncate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Truncate table before load (default: true). Use --no-truncate to upsert on (state, location, type).",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        loaded, skipped = load_rows(args.csv, truncate=args.truncate)

    print(f"Loaded {loaded} rows into sales_tax_rates (skipped {skipped})")


if __name__ == "__main__":
    main()
