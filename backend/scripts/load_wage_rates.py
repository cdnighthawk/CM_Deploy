"""Load wage_rates from CSV (standalone script; run from backend directory)."""
from __future__ import annotations

import argparse
import csv
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from sqlalchemy import func, text  # noqa: E402
from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.wage_rate import WageRate  # noqa: E402, F401  (register mapper)


DEFAULT_CSV = str(database_files_dir() / "all_wage_rates.csv")


def _blank_to_none(s: str | None) -> str | None:
    if s is None:
        return None
    stripped = s.strip()
    return None if stripped == "" else stripped


def _parse_decimal(raw: str | None) -> Decimal | None:
    s = _blank_to_none(raw)
    if s is None:
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        return None


def _normalize_row_keys(row: dict[str, str]) -> dict[str, str]:
    return {k.strip().lower(): (v if v is not None else "") for k, v in row.items()}


def _row_to_values(norm: dict[str, str]) -> dict:
    sub_raw = norm.get("sub_area", "")
    sub_area = "" if (sub_raw is None or str(sub_raw).strip() == "") else str(sub_raw).strip()

    notes_val = _blank_to_none(norm.get("notes", ""))
    notes_lower = (notes_val or "").lower()
    is_assumed = "assumed" in notes_lower

    year_raw = _blank_to_none(norm.get("year", ""))
    year = int(year_raw) if year_raw is not None else 0

    out: dict = {
        "state": (norm.get("state") or "").strip(),
        "sub_area": sub_area,
        "year": year,
        "trade": (norm.get("trade") or "").strip(),
        "basic_hourly_rate": _parse_decimal(norm.get("basic_hourly_rate")),
        "health_welfare": _parse_decimal(norm.get("health_welfare")),
        "pension": _parse_decimal(norm.get("pension")),
        "vacation_holiday": _parse_decimal(norm.get("vacation_holiday")),
        "other_payments": _parse_decimal(norm.get("other_payments")),
        "training": _parse_decimal(norm.get("training")),
        "notes": notes_val,
        "is_assumed": is_assumed,
    }
    return out


def _upsert_row(values: dict) -> None:
    table = WageRate.__table__
    stmt = insert(table).values(**values)
    update_cols = {
        "basic_hourly_rate": stmt.excluded.basic_hourly_rate,
        "health_welfare": stmt.excluded.health_welfare,
        "pension": stmt.excluded.pension,
        "vacation_holiday": stmt.excluded.vacation_holiday,
        "other_payments": stmt.excluded.other_payments,
        "training": stmt.excluded.training,
        "notes": stmt.excluded.notes,
        "is_assumed": stmt.excluded.is_assumed,
        "updated_at": func.now(),
    }
    stmt = stmt.on_conflict_do_update(
        constraint="uq_wage_rates_state_sub_area_year_trade",
        set_=update_cols,
    )
    db.session.execute(stmt)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load wage_rates from CSV.")
    parser.add_argument(
        "--csv",
        default=DEFAULT_CSV,
        help="Path to all_wage_rates.csv",
    )
    parser.add_argument(
        "--truncate",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="TRUNCATE wage_rates before load (default: true)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        if args.truncate:
            db.session.execute(text("TRUNCATE wage_rates RESTART IDENTITY"))
            db.session.commit()

        count = 0
        with open(args.csv, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for raw_row in reader:
                norm = _normalize_row_keys(raw_row)
                values = _row_to_values(norm)
                if args.truncate:
                    db.session.add(WageRate(**values))
                else:
                    _upsert_row(values)
                count += 1

        db.session.commit()
        print(f"Loaded {count} rows into wage_rates")


if __name__ == "__main__":
    main()
