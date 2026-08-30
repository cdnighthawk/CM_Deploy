"""Create Drawing rows for B2 objects that already include a job number.

Does not upload or download PDFs. UUID-only keys are skipped.

Usage (from backend/):
    python scripts/link_b2_drawings.py --dry-run
    python scripts/link_b2_drawings.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

load_dotenv(_BACKEND / ".env", override=True)

if "--local" in sys.argv:
    local = (os.environ.get("LOCAL_DATABASE_URL") or "").strip()
    if local:
        os.environ["DATABASE_URL"] = local
        os.environ["_USIS_FORCE_LOCAL_DB"] = "1"
        import dotenv as _dotenv

        _orig_load = _dotenv.load_dotenv

        def _keep_local_db(*args, **kwargs):
            result = _orig_load(*args, **kwargs)
            forced = (os.environ.get("LOCAL_DATABASE_URL") or "").strip()
            if forced:
                os.environ["DATABASE_URL"] = forced
            return result

        _dotenv.load_dotenv = _keep_local_db

from app.script_env import skip_startup_lead_bootstrap

skip_startup_lead_bootstrap()


def main() -> int:
    parser = argparse.ArgumentParser(description="Link B2 job-path drawings to projects.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--local",
        action="store_true",
        help="Use LOCAL_DATABASE_URL even if DATABASE_URL is set.",
    )
    parser.add_argument(
        "--existing-only",
        action="store_true",
        help="Do not create a project row when the job number is missing.",
    )
    parser.add_argument(
        "--jobs",
        default="",
        help="Comma-separated job numbers to link (default: all job-path keys).",
    )
    parser.add_argument(
        "--repair-sheets",
        action="store_true",
        help="Rewrite sheet numbers on already-linked B2 rows from the filename.",
    )
    args = parser.parse_args()
    if args.local:
        local = (os.environ.get("LOCAL_DATABASE_URL") or "").strip()
        if not local:
            print("LOCAL_DATABASE_URL is not set.", file=sys.stderr)
            return 2
        os.environ["DATABASE_URL"] = local

    from app import create_app
    from app.extensions import db
    from app.services.b2_project_link import register_b2_job_files, repair_b2_sheet_numbers

    app = create_app()
    with app.app_context():
        wanted = {n.strip() for n in args.jobs.split(",") if n.strip()}
        payload = register_b2_job_files(
            dry_run=args.dry_run,
            create_missing=not args.existing_only,
            job_numbers=wanted or None,
        )
        if args.repair_sheets and not args.dry_run:
            payload["sheet_repair"] = repair_b2_sheet_numbers()
        if not args.dry_run:
            db.session.commit()
        print(json.dumps(payload, indent=2, default=str))
    return 0 if payload.get("error") is None else 2


if __name__ == "__main__":
    raise SystemExit(main())
