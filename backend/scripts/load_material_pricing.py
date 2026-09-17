"""Load material_pricing rows from Bobrick / updated vendor material CSV exports.

Repo-seed CSVs under ``backend/data/catalog`` (JL Industries cabinets,
Construction Specialties, Inpro wall protection, later Claridge, …) upsert
by (manufacturer, item) and never truncate the table. Blank seed labor does not
overwrite hours already on a row. Use ``--replace-manufacturer`` to swap one
vendor family and keep unique SKU labor.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = Path(__file__).resolve().parent
for _p in (_BACKEND_ROOT, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir, repo_catalog_seed_csvs  # noqa: E402
from material_csv_row import (  # noqa: E402
    CatalogOldRow,
    is_target_manufacturer,
    plan_manufacturer_replace,
    read_material_csv,
)

_DEFAULT_BOBRICK = database_files_dir() / "BOBRICK MATERIAL PRICING.CSV"
_DEFAULT_UPDATED = database_files_dir() / "uPDATED PRICING.CSV"


def should_truncate_catalog_file(
    *,
    index: int,
    is_repo_seed: bool,
    truncate_flag: bool | None,
    all_defaults: bool,
    repo_seeds_only: bool,
    path_count: int,
) -> bool:
    """Repo seeds upsert unless the operator passed an explicit --truncate."""
    if truncate_flag is not None:
        return bool(truncate_flag) and index == 0
    if is_repo_seed:
        return False
    if all_defaults:
        return index == 0
    if repo_seeds_only:
        return False
    return path_count == 1


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
                "labor_per": func.coalesce(ins.excluded.labor_per, table.c.labor_per),
                "size_width_in": func.coalesce(ins.excluded.size_width_in, table.c.size_width_in),
                "size_height_in": func.coalesce(ins.excluded.size_height_in, table.c.size_height_in),
                "currency": ins.excluded.currency,
                "unit_of_measure": ins.excluded.unit_of_measure,
                "updated_at": func.now(),
            },
        )
        db.session.execute(stmt)
    db.session.commit()


def replace_manufacturer_rows(
    db,
    MaterialPrice,
    payloads: list[dict[str, object]],
    manufacturer: str,
    *,
    delete_leftovers: bool = True,
):
    """Replace or merge one manufacturer family; copy unique SKU labor; do not truncate."""
    from datetime import datetime, timezone

    from sqlalchemy import func, select

    from material_csv_row import manufacturer_aliases

    aliases = sorted(manufacturer_aliases(manufacturer))
    if not aliases:
        raise ValueError("replace manufacturer is empty")
    old_models = db.session.scalars(
        select(MaterialPrice).where(func.lower(MaterialPrice.manufacturer).in_(aliases))
    ).all()
    old_rows = [
        CatalogOldRow(
            id=row.id,
            manufacturer=row.manufacturer,
            item=row.item,
            labor_per=row.labor_per,
        )
        for row in old_models
        if is_target_manufacturer(row.manufacturer, manufacturer)
    ]
    plan = plan_manufacturer_replace(old_rows, payloads, manufacturer)

    if delete_leftovers:
        for uid in plan.delete_ids:
            row = db.session.get(MaterialPrice, uid)
            if row is not None:
                db.session.delete(row)
        db.session.flush()
    else:
        plan.delete_ids = []

    now = datetime.now(timezone.utc)
    for uid, fields in plan.updates:
        row = db.session.get(MaterialPrice, uid)
        if row is None:
            continue
        for key, value in fields.items():
            setattr(row, key, value)
        row.updated_at = now
    db.session.flush()

    for payload in plan.inserts:
        db.session.add(MaterialPrice(**payload))
    db.session.commit()
    return plan


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
        help="Load BOBRICK (truncate) then uPDATED PRICING (upsert) from DATABASE_FILES_ROOT, "
        "then upsert in-repo catalog seeds.",
    )
    parser.add_argument(
        "--repo-seeds",
        action="store_true",
        help="Upsert CSVs from backend/data/catalog (never truncates unless --truncate).",
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
    parser.add_argument(
        "--replace-manufacturer",
        default="",
        help="Replace rows for this manufacturer only (CS aliases included). "
        "Keeps unique SKU labor hours. Does not truncate the table.",
    )
    parser.add_argument(
        "--merge-manufacturer",
        default="",
        help="Upsert this manufacturer from CSV and copy unique SKU labor. "
        "Does not delete leftover rows (use for adding a CS product family).",
    )
    args = parser.parse_args()
    replace_mfr = (args.replace_manufacturer or "").strip()
    merge_mfr = (args.merge_manufacturer or "").strip()
    family_mfr = replace_mfr or merge_mfr
    if replace_mfr and merge_mfr:
        parser.error("use either --replace-manufacturer or --merge-manufacturer")
    if family_mfr:
        if args.all_defaults:
            parser.error("manufacturer replace/merge cannot be combined with --all-defaults")
        if args.truncate:
            parser.error("manufacturer replace/merge cannot truncate the catalog")
        if not args.csv_paths:
            parser.error("manufacturer replace/merge requires --csv")
        if args.repo_seeds:
            parser.error("manufacturer replace/merge cannot be combined with --repo-seeds")
        if len(args.csv_paths) != 1:
            parser.error("manufacturer replace/merge accepts exactly one --csv file")

    from sqlalchemy import text

    from app.script_env import skip_startup_lead_bootstrap

    skip_startup_lead_bootstrap()

    from app import create_app
    from app.extensions import db
    from app.models.material_pricing import MaterialPrice

    app = create_app()
    if family_mfr:
        uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        if "CHANGE_ME_APP_PASSWORD" in uri:
            raise SystemExit(
                "Set DATABASE_URL to the Render usis-cm-db External URL "
                "before manufacturer replace/merge."
            )

    seed_paths = repo_catalog_seed_csvs()
    seed_set = {p.resolve() for p in seed_paths}

    if family_mfr:
        paths = [Path(p) for p in args.csv_paths]
    elif args.all_defaults:
        paths = [_DEFAULT_BOBRICK, _DEFAULT_UPDATED, *seed_paths]
    elif args.csv_paths:
        paths = [Path(p) for p in args.csv_paths]
        if args.repo_seeds:
            paths.extend(seed_paths)
    elif args.repo_seeds:
        paths = list(seed_paths)
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
            if family_mfr:
                plan = replace_manufacturer_rows(
                    db,
                    MaterialPrice,
                    payloads,
                    family_mfr,
                    delete_leftovers=bool(replace_mfr),
                )
                verb = "Replaced" if replace_mfr else "Merged"
                print(
                    f"{verb} {family_mfr} from {csv_path.name}: "
                    f"{plan.updated_count} updated, {plan.inserted_count} inserted, "
                    f"{plan.deleted_count} deleted, {plan.labor_copied} labor copied, "
                    f"{plan.unmatched_new} unmatched new, "
                    f"{len(plan.ambiguous_keys)} ambiguous"
                )
                if plan.ambiguous_keys:
                    print("Ambiguous SKUs (labor not copied): " + ", ".join(plan.ambiguous_keys[:40]))
                total += len(payloads)
                continue
            is_repo_seed = csv_path.resolve() in seed_set
            do_truncate = should_truncate_catalog_file(
                index=i,
                is_repo_seed=is_repo_seed,
                truncate_flag=args.truncate,
                all_defaults=bool(args.all_defaults),
                repo_seeds_only=bool(args.repo_seeds) and not args.csv_paths,
                path_count=len(paths),
            )

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
