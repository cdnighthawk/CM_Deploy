"""Import HubSpot CRM contacts export into ``companies`` and ``contacts``.

Expects a CSV with columns like HubSpot's default export:
``First Name``, ``Last Name``, ``Email``, ``Phone Number``, ``Company Name``, …

Usage (from ``backend/``)::

    python scripts/load_hubspot_contacts.py
    python scripts/load_hubspot_contacts.py --csv "E:\\path\\to\\export.csv"

Defaults: ``HUBSPOT_CONTACTS_CSV`` env, else the newest ``hubspot-crm-exports-*.csv``
under ``DATABASE_FILES_ROOT`` (see ``scripts/db_csv_paths.py``).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
_BACKEND = _SCRIPTS.parent
for _p in (_BACKEND, _SCRIPTS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from db_csv_paths import database_files_dir  # noqa: E402

from app.script_env import skip_startup_lead_bootstrap  # noqa: E402

skip_startup_lead_bootstrap()

from sqlalchemy import func, select  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.company import Company, Contact  # noqa: E402


def _default_csv_path() -> str:
    env = (os.environ.get("HUBSPOT_CONTACTS_CSV") or "").strip()
    if env and Path(env).is_file():
        return env
    d = database_files_dir()
    matches = sorted(d.glob("hubspot-crm-exports-*.csv"))
    if matches:
        return str(matches[-1])
    return str(d / "hubspot-crm-exports-all-contacts-2026-04-09.csv")


def _norm(s: str | None) -> str | None:
    if s is None:
        return None
    t = str(s).strip()
    return t if t else None


def load_hubspot_csv(csv_path: Path) -> tuple[int, int, int]:
    """Returns ``(companies_created, contacts_upserted, rows_skipped)``."""
    if not csv_path.is_file():
        raise FileNotFoundError(str(csv_path))

    companies_created = 0
    contacts_upserted = 0
    skipped = 0

    with csv_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row")

        for raw in reader:
            email = _norm(raw.get("Email"))
            if not email:
                skipped += 1
                continue

            fn = _norm(raw.get("First Name")) or ""
            ln = _norm(raw.get("Last Name")) or ""
            phone = _norm(raw.get("Phone Number"))
            company_name = _norm(raw.get("Company Name"))

            company_id = None
            if company_name:
                existing_co = db.session.scalar(
                    select(Company).where(func.lower(Company.name) == company_name.lower())
                )
                if existing_co:
                    company_id = existing_co.id
                else:
                    co = Company(
                        name=company_name,
                        company_type="other",
                        phone=None,
                        email=None,
                    )
                    db.session.add(co)
                    db.session.flush()
                    company_id = co.id
                    companies_created += 1

            existing_ct = db.session.scalar(
                select(Contact).where(func.lower(Contact.email) == email.lower())
            )
            if existing_ct:
                if fn:
                    existing_ct.first_name = fn
                if ln:
                    existing_ct.last_name = ln
                if phone:
                    existing_ct.phone = phone
                if company_id is not None:
                    existing_ct.company_id = company_id
            else:
                db.session.add(
                    Contact(
                        company_id=company_id,
                        first_name=fn or None,
                        last_name=ln or None,
                        email=email,
                        phone=phone,
                    )
                )
            contacts_upserted += 1

    db.session.commit()
    return companies_created, contacts_upserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description="Load HubSpot contacts CSV into companies/contacts.")
    parser.add_argument(
        "--csv",
        default=_default_csv_path(),
        help="Path to HubSpot contacts export CSV",
    )
    args = parser.parse_args()
    path = Path(args.csv)

    app = create_app()
    with app.app_context():
        created, upserted, skipped = load_hubspot_csv(path)

    print(
        f"HubSpot import done: companies_created={created} "
        f"contacts_touched={upserted} rows_skipped_no_email={skipped} file={path}"
    )


if __name__ == "__main__":
    main()
