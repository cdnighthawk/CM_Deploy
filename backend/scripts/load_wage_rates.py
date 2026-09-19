"""Load wage_rates from CSV (standalone script; run from backend directory)."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.api._wage_rate_service import import_wage_rates_csv  # noqa: E402
from app.models.wage_rate import WageRate  # noqa: E402, F401  (register mapper)


DEFAULT_CSV = str(database_files_dir() / "all_wage_rates.csv")


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
        help="Replace existing wage_rates before load (default: true)",
    )
    args = parser.parse_args()

    app = create_app()
    with app.app_context():
        text = Path(args.csv).read_text(encoding="utf-8-sig")
        result = import_wage_rates_csv(text, replace=bool(args.truncate))
        print(
            f"Loaded {result['total']} rows into wage_rates "
            f"(created {result['created']}, updated {result['updated']}, skipped {result['skipped']})"
        )


if __name__ == "__main__":
    main()
