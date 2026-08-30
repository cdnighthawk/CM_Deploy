"""Ingest one-PDF-per-sheet files from a job/discipline/set folder tree.

Folder layout (either is accepted):

    {root}/{job}/{Discipline}/{Set}/{SheetToken}_{Title}.pdf
    {root}/{Discipline}/{Set}/{SheetToken}_{Title}.pdf   (pass --job)

Usage (from backend/):
    python scripts/ingest_drawings.py --root D:\\drawings --dry-run
    python scripts/ingest_drawings.py --root D:\\drawings --local --execute
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import dotenv as _dotenv

_dotenv.load_dotenv(_BACKEND / ".env", override=True)
os.environ["USIS_BOOTSTRAP_LEADS_ON_STARTUP"] = "0"

from werkzeug.datastructures import FileStorage

from app.script_env import skip_startup_lead_bootstrap
from app.services.drawing_label import label_drawing, parse_folder_path
from app.services.drawing_upload import DrawingUploadError, upload_project_drawing_pdf
from app.services.b2_project_link import resolve_project_id_for_number

skip_startup_lead_bootstrap()


def _iter_pdfs(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.pdf") if p.is_file())


def _public(d) -> dict:
    return {
        "id": str(d.id),
        "sheet_number": d.sheet_number,
        "sheet_title": d.sheet_title,
        "discipline": d.discipline,
        "drawing_set": d.drawing_set,
        "revision": d.revision,
        "label_status": d.label_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Folder tree of PDFs.")
    parser.add_argument("--job", default="", help="Job number when the root does not include it.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--local", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    if args.local:
        local = (os.environ.get("LOCAL_DATABASE_URL") or "").strip()
        if local:
            os.environ["DATABASE_URL"] = local

    from app import create_app
    from app.extensions import db

    app = create_app()
    planned: list[dict] = []
    created = 0
    errors: list[str] = []
    with app.app_context():
        for path in _iter_pdfs(root):
            rel = str(path.relative_to(root)).replace("\\", "/")
            folder = parse_folder_path(rel)
            job = (args.job or folder.get("job") or "").strip()
            if not job:
                errors.append(f"{rel}: no job number (use --job or put job in the path)")
                continue
            labels = label_drawing(
                filename=path.name,
                folder_path=rel,
                discipline=folder.get("discipline"),
                drawing_set=folder.get("drawing_set"),
            )
            item = {"path": rel, "job": job, **labels}
            planned.append(item)
            if not args.execute:
                continue
            pid = resolve_project_id_for_number(job, create_missing=True)
            if pid is None:
                errors.append(f"{rel}: could not resolve project {job}")
                continue
            with path.open("rb") as fh:
                storage = FileStorage(stream=fh, filename=path.name, content_type="application/pdf")
                try:
                    upload_project_drawing_pdf(
                        project_id=pid,
                        file_storage=storage,
                        sheet_number=labels["sheet_number"],
                        sheet_title=labels["sheet_title"],
                        discipline=labels["discipline"],
                        drawing_set=labels["drawing_set"],
                        revision=labels["revision"] or "0",
                        split_pages=False,
                        max_bytes=52_428_800,
                        drawing_public_fn=_public,
                    )
                    created += 1
                except DrawingUploadError as exc:
                    errors.append(f"{rel}: {exc.message}")
        if args.execute:
            db.session.commit()
    print(
        json.dumps(
            {
                "root": str(root),
                "dry_run": not args.execute,
                "planned": len(planned),
                "created": created,
                "errors": errors,
                "items": planned[:50],
            },
            indent=2,
        )
    )
    return 2 if errors and args.execute else 0


if __name__ == "__main__":
    raise SystemExit(main())
