"""Load company cost codes from a CSI Code/Title/Level CSV."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from app import create_app  # noqa: E402
from app.api._cost_code_service import import_company_cost_codes_csv  # noqa: E402

DEFAULT_CSV = str(database_files_dir() / "JobCost Codes.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path(DEFAULT_CSV),
        help=f"Path to Code/Title/Level CSV (default: {DEFAULT_CSV})",
    )
    args = parser.parse_args()
    path = args.csv
    if not path.is_file():
        print(f"CSV not found: {path}", file=sys.stderr)
        raise SystemExit(1)

    text = path.read_text(encoding="utf-8-sig")
    app = create_app()
    with app.app_context():
        result = import_company_cost_codes_csv(text)

    print(
        f"Imported {result['total']} company cost codes "
        f"({result['created']} created, {result['updated']} updated)"
    )


if __name__ == "__main__":
    main()
