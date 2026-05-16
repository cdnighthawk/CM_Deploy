"""Load material_pricing rows from Bobrick / updated vendor material CSV exports."""
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
from material_csv_row import read_material_csv  # noqa: E402

_DEFAULT_BOBRICK = database_files_dir() / "BOBRICK MATERIAL PRICING.CSV"
_DEFAULT_UPDATED = database_files_dir() / "uPDATED PRICING.CSV"


def _upsert_payloads(db, MaterialPrice, payloads: list[dict[str, object]]) -> None:
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy.sql import func

    table = MaterialPrice.__table__
    for p in payloads:
        ins = pg_insert(table).values(**p)
        stmt = ins.on_conflict_do_update(
            index_elements=["manufacturer", "item"],
            set_={
                "category": ins.excluded.category,
                "csi_spec_section": ins.excluded.csi_spec_section,
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Load material_pricing from CSV.")
    parser.add_argument(
        "--csv",
        action="append",
        dest="csv_paths",
        help="Path to a source CSV (repeat for multiple files).",
    )
    parser.add_argument(
        "--all-defaults",
        action="store_true",
        help="Load BOBRICK (truncate) then uPDATED PRICING (upsert) from DATABASE_FILES_ROOT.",
    )
    parser.add_argument(
        "--truncate",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Truncate table before load. Default: true for first file only when using --all-defaults.",
    )
    parser.add_argument(
        "--tag-door-hardware",
        action="store_true",
        help="Set csi_spec_section=087100 (08 71 00) on every row in this load.",
    )
    args = parser.parse_args()

    from sqlalchemy import text

    from app.script_env import skip_startup_lead_bootstrap

    skip_startup_lead_bootstrap()

    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice

    app = create_app()

    if args.all_defaults:
        paths = [_DEFAULT_BOBRICK, _DEFAULT_UPDATED]
    elif args.csv_paths:
        paths = [Path(p) for p in args.csv_paths]
    else:
        paths = [_DEFAULT_BOBRICK]

    with app.app_context():
        total = 0
        for i, csv_path in enumerate(paths):
            if not csv_path.is_file():
                print(f"Skipping missing CSV: {csv_path}")
                continue
            payloads = read_material_csv(csv_path)
            if args.tag_door_hardware:
                for p in payloads:
                    p["csi_spec_section"] = "087100"
            if args.truncate is not None:
                do_truncate = bool(args.truncate) and i == 0
            elif args.all_defaults:
                do_truncate = i == 0
            elif len(paths) == 1:
                do_truncate = True
            else:
                do_truncate = False

            if do_truncate:
                db.session.execute(text("TRUNCATE material_pricing RESTART IDENTITY"))
                db.session.commit()
                db.session.bulk_insert_mappings(MaterialPrice, payloads)
                db.session.commit()
            else:
                _upsert_payloads(db, MaterialPrice, payloads)
            print(f"Loaded {len(payloads)} rows from {csv_path.name}")
            total += len(payloads)

    print(f"Done — {total} row(s) processed across {len(paths)} file(s).")


if __name__ == "__main__":
    main()
