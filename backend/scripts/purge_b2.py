"""Delete every B2 object and every database row that pointed at B2.

Usage (from backend/):
    python scripts/purge_b2.py --local --execute
    python scripts/purge_b2.py --execute --i-know-this-is-production
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import dotenv as _dotenv

_dotenv.load_dotenv(_BACKEND / ".env", override=True)

from sqlalchemy import text

from _script_db_guard import require_safe_execute

os.environ["USIS_BOOTSTRAP_LEADS_ON_STARTUP"] = "0"


def _force_database_url(url: str) -> None:
    if "sslmode=" not in url and "render.com" in url:
        url = url + ("&" if "?" in url else "?") + "sslmode=require"
    os.environ["DATABASE_URL"] = url
    os.environ.pop("LOCAL_DATABASE_URL", None)
    os.environ["FLASK_ENV"] = "production" if "render.com" in url else os.environ.get("FLASK_ENV", "development")

    _orig = _dotenv.load_dotenv

    def _keep(*args, **kwargs):
        result = _orig(*args, **kwargs)
        os.environ["DATABASE_URL"] = url
        if "render.com" in url:
            os.environ.pop("LOCAL_DATABASE_URL", None)
            os.environ["FLASK_ENV"] = "production"
        return result

    _dotenv.load_dotenv = _keep


def _b2_ids_sql() -> str:
    return """
        SELECT id
        FROM documents
        WHERE coalesce(tags->>'storage_object', '') <> ''
           OR coalesce(tags->>'linked_from', '') = 'b2_key'
    """


def _probe(db) -> dict:
    docs = db.session.execute(text(f"SELECT count(*) FROM ({_b2_ids_sql()}) t")).scalar()
    drawings = db.session.execute(
        text(
            f"""
            SELECT count(*)
            FROM drawings dr
            WHERE dr.id IN ({_b2_ids_sql()})
            """
        )
    ).scalar()
    by_type = db.session.execute(
        text(
            f"""
            SELECT document_type::text, count(*)
            FROM documents
            WHERE id IN ({_b2_ids_sql()})
            GROUP BY 1
            ORDER BY 2 DESC
            """
        )
    ).fetchall()
    return {
        "b2_documents": int(docs or 0),
        "b2_drawings": int(drawings or 0),
        "by_type": [(r[0], int(r[1])) for r in by_type],
    }


def _table_exists(db, name: str) -> bool:
    return bool(
        db.session.execute(
            text("SELECT to_regclass(:n) IS NOT NULL"),
            {"n": f"public.{name}"},
        ).scalar()
    )


def _null_drawing_refs(db, table: str, ids: list) -> int:
    if not _table_exists(db, table):
        return 0
    cols = db.session.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :t AND column_name = 'drawing_id'
            """
        ),
        {"t": table},
    ).first()
    if cols is None:
        return 0
    rows = db.session.execute(
        text(f"UPDATE {table} SET drawing_id = NULL WHERE drawing_id = ANY(:ids) RETURNING id"),
        {"ids": ids},
    ).fetchall()
    return len(rows)


def _purge_db_rows(db) -> dict:
    ids = [row[0] for row in db.session.execute(text(_b2_ids_sql())).fetchall()]
    if not ids:
        return {"deleted_documents": 0, "nulled_takeoff": 0, "nulled_rfis": 0, "nulled_photos": 0}
    takeoff = _null_drawing_refs(db, "takeoff_line_items", ids)
    rfis = _null_drawing_refs(db, "rfis", ids)
    photos = _null_drawing_refs(db, "field_photos", ids)
    issues = _null_drawing_refs(db, "tracker_issues", ids)
    db.session.execute(text("DELETE FROM documents WHERE id = ANY(:ids)"), {"ids": ids})
    return {
        "deleted_documents": len(ids),
        "nulled_takeoff": takeoff,
        "nulled_rfis": rfis,
        "nulled_photos": photos,
        "nulled_issues": issues,
    }


def _delete_all_b2() -> dict:
    from flask import current_app

    from app.services.object_storage import _s3_client, b2_enabled

    if not b2_enabled():
        return {"error": "b2_disabled", "deleted": 0, "listed": 0}
    client = _s3_client()
    bucket = current_app.config["B2_BUCKET_NAME"]
    listed = 0
    deleted = 0
    errors: list[str] = []
    paginator = client.get_paginator("list_objects_v2")
    batch: list[dict[str, str]] = []
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents") or []:
            key = obj.get("Key") or ""
            if not key or key.endswith("/"):
                continue
            listed += 1
            batch.append({"Key": key})
            if len(batch) >= 1000:
                resp = client.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
                deleted += len(batch) - len(resp.get("Errors") or [])
                for err in resp.get("Errors") or []:
                    errors.append(f"{err.get('Key')}: {err.get('Code')}")
                batch = []
    if batch:
        resp = client.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
        deleted += len(batch) - len(resp.get("Errors") or [])
        for err in resp.get("Errors") or []:
            errors.append(f"{err.get('Key')}: {err.get('Code')}")
    remaining = 0
    for page in paginator.paginate(Bucket=bucket):
        remaining += len([o for o in (page.get("Contents") or []) if o.get("Key") and not o["Key"].endswith("/")])
    return {
        "listed": listed,
        "deleted": deleted,
        "remaining": remaining,
        "errors": errors[:20],
        "error_count": len(errors),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe B2 objects and B2-backed database rows.")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--i-know-this-is-production", action="store_true")
    parser.add_argument("--skip-b2", action="store_true", help="Only delete database rows.")
    parser.add_argument("--skip-db", action="store_true", help="Only delete B2 objects.")
    args = parser.parse_args()

    if args.local:
        local = (os.environ.get("LOCAL_DATABASE_URL") or os.environ.get("DATABASE_URL") or "").strip()
        if not local:
            print("LOCAL_DATABASE_URL is not set.", file=sys.stderr)
            return 2
        _force_database_url(local)
        os.environ["FLASK_ENV"] = "development"
    elif (os.environ.get("RENDER_DATABASE_URL") or "").strip():
        _force_database_url(os.environ["RENDER_DATABASE_URL"].strip())

    require_safe_execute(
        execute=args.execute,
        production_ack=args.i_know_this_is_production,
        script_name="purge_b2.py",
    )

    from app import create_app
    from app.config import _env_database_url
    from app.extensions import db

    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = _env_database_url()
    with app.app_context():
        uri = str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")
        host = urlparse(uri).hostname or ""
        before = _probe(db)
        print(json.dumps({"db_host": host, "before": before}, indent=2, default=str))
        if not args.execute:
            print(json.dumps({"dry_run": True}, indent=2))
            return 0
        out: dict = {"db_host": host, "before": before}
        if not args.skip_b2:
            out["b2"] = _delete_all_b2()
        if not args.skip_db:
            db.session.rollback()
            out["db"] = _purge_db_rows(db)
            db.session.commit()
        out["after"] = _probe(db)
        print(json.dumps(out, indent=2, default=str))
        if out.get("b2", {}).get("error") == "b2_disabled":
            return 2
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
