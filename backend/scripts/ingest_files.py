"""Ingest a folder tree of drawings and documents in bulk.

Points at the production ingest API by default, or runs in-process with --local.
Sheet-like PDFs become drawings; everything else becomes a document. Failed
uploads retry on 502/503/504/timeout. A JSONL manifest lets you resume.

Usage (from backend/):
    python scripts/ingest_files.py --root D:\\drawings --dry-run
    python scripts/ingest_files.py --root D:\\drawings --job 24060 --execute
    python scripts/ingest_files.py --root D:\\dump --base-url https://www.usiscm.com --execute
    python scripts/ingest_files.py --root D:\\dump --local --execute --workers 1
"""
from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
_SCRIPTS = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import dotenv as _dotenv

_dotenv.load_dotenv(_BACKEND / ".env", override=True)
os.environ["USIS_BOOTSTRAP_LEADS_ON_STARTUP"] = "0"

from app.script_env import skip_startup_lead_bootstrap
from app.services.ingest_classify import classify_ingest_file, should_skip_path

skip_startup_lead_bootstrap()

_MAX_BYTES = 52_428_800
_RETRY_STATUSES = frozenset({429, 502, 503, 504})
_DONE = frozenset({"created", "duplicate", "skipped"})


def _iter_files(root: Path) -> list[Path]:
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = str(path.relative_to(root)).replace("\\", "/")
        if should_skip_path(rel):
            continue
        found.append(path)
    return sorted(found)


def _mime_for(path: Path) -> str:
    guessed, _ = mimetypes.guess_type(path.name)
    if guessed:
        return guessed
    if path.suffix.lower() == ".pdf":
        return "application/pdf"
    return "application/octet-stream"


def _load_manifest(path: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        rel = str(item.get("path") or "").replace("\\", "/").strip()
        if rel:
            rows[rel] = item
    return rows


def _append_manifest(path: Path, item: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(item, ensure_ascii=False) + "\n")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _plan_item(path: Path, root: Path, args: argparse.Namespace) -> dict[str, Any]:
    rel = str(path.relative_to(root)).replace("\\", "/")
    classified = classify_ingest_file(rel, kind=args.kind)
    size = path.stat().st_size
    item: dict[str, Any] = {
        "path": rel,
        "kind": classified["kind"],
        "document_type": classified["document_type"],
        "bytes": size,
    }
    if size > args.max_bytes:
        item["status"] = "error"
        item["error"] = f"file too large (max {args.max_bytes} bytes)"
        return item
    item["status"] = "planned"
    return item


def _metadata(item: dict[str, Any], args: argparse.Namespace, checksum: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "filename": Path(item["path"]).name,
        "relative_path": item["path"],
        "source": "mass_ingest",
        "source_id": item["path"],
        "content_hash": checksum,
        "document_type": item["document_type"],
        "split_pages": bool(args.split_pages),
    }
    if args.project_id:
        meta["project_id"] = args.project_id
    if args.lead_estimate_id:
        meta["lead_estimate_id"] = args.lead_estimate_id
    if args.job:
        meta["project_number"] = args.job
        meta["folder_name"] = args.job
    elif "/" in item["path"]:
        meta["folder_name"] = item["path"].split("/", 1)[0]
    return meta


def _ingest_local(path: Path, item: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    from werkzeug.datastructures import FileStorage

    from app.extensions import db
    from app.services.ingest import IngestError, handle_ingest_upload

    checksum = _sha256(path)
    meta = _metadata(item, args, checksum)
    with path.open("rb") as fh:
        storage = FileStorage(stream=fh, filename=path.name, content_type=_mime_for(path))
        try:
            body, status = handle_ingest_upload(storage, meta, kind=item["kind"])
            db.session.commit()
        except IngestError as exc:
            db.session.rollback()
            return {**item, "status": "error", "error": exc.message, "http_status": exc.status}
        except Exception as exc:
            db.session.rollback()
            return {**item, "status": "error", "error": str(exc)}
    return _from_body(item, body, status)


def _from_body(item: dict[str, Any], body: dict[str, Any], status: int) -> dict[str, Any]:
    doc = body.get("drawing") or body.get("document") or {}
    result = {
        **item,
        "status": "duplicate" if body.get("duplicate") else "created",
        "id": doc.get("id") or doc.get("document_id") or doc.get("drawing_id"),
        "project_id": (body.get("project") or {}).get("project_id") or doc.get("project_id"),
        "matched_by": body.get("matchedBy"),
        "http_status": status,
    }
    if body.get("count"):
        result["count"] = body["count"]
    return result


def _ingest_remote(path: Path, item: dict[str, Any], args: argparse.Namespace, client) -> dict[str, Any]:
    checksum = _sha256(path)
    meta = _metadata(item, args, checksum)
    kind = item["kind"]
    url = args.base_url.rstrip("/") + ("/api/drawings" if kind == "drawing" else "/api/documents")
    last_error = "upload failed"
    last_status = 0
    for attempt in range(1, args.retries + 1):
        try:
            with path.open("rb") as fh:
                response = client.post(
                    url,
                    headers={"Authorization": f"Bearer {args.api_key}"},
                    data={"metadata": json.dumps(meta), "kind": kind, "content_hash": checksum},
                    files={"file": (path.name, fh, _mime_for(path))},
                    timeout=args.timeout,
                )
            last_status = response.status_code
            if response.status_code in _RETRY_STATUSES:
                last_error = f"HTTP {response.status_code}"
                time.sleep(min(30, 2 ** (attempt - 1)))
                continue
            try:
                body = response.json()
            except Exception:
                body = {}
            if response.status_code in (200, 201) and isinstance(body, dict):
                return _from_body(item, body, response.status_code)
            last_error = str((body or {}).get("error") or response.text or f"HTTP {response.status_code}")[:500]
            if response.status_code < 500:
                break
        except Exception as exc:
            last_error = str(exc)
            time.sleep(min(30, 2 ** (attempt - 1)))
    return {**item, "status": "error", "error": last_error, "http_status": last_status}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Folder tree to walk.")
    parser.add_argument("--job", default="", help="Project number when folders do not include it.")
    parser.add_argument("--project-id", default="", help="Workspace / job UUID.")
    parser.add_argument("--lead-estimate-id", default="", help="Lead UUID.")
    parser.add_argument("--kind", choices=("auto", "drawing", "document"), default="auto")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--local", action="store_true", help="Write through the local Flask app.")
    parser.add_argument("--base-url", default="", help="Ingest API origin (Bearer).")
    parser.add_argument("--api-key", default="", help="CM_API_KEY / CM_INGEST_API_KEY.")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--max-bytes", type=int, default=_MAX_BYTES)
    parser.add_argument("--split-pages", action="store_true")
    parser.add_argument("--manifest", default="", help="JSONL resume file (default: <root>/.ingest-manifest.jsonl).")
    parser.add_argument("--limit", type=int, default=0, help="Ingest at most N files (after skip).")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Not a directory: {root}", file=sys.stderr)
        return 2

    args.job = (args.job or "").strip()
    args.project_id = (args.project_id or "").strip()
    args.lead_estimate_id = (args.lead_estimate_id or "").strip()
    args.base_url = (args.base_url or os.environ.get("USIS_INGEST_URL") or "https://www.usiscm.com").strip()
    args.api_key = (args.api_key or os.environ.get("CM_INGEST_API_KEY") or os.environ.get("CM_API_KEY") or "").strip()
    args.workers = max(1, min(int(args.workers), 8))
    args.retries = max(1, min(int(args.retries), 12))
    manifest_path = Path(args.manifest).expanduser() if args.manifest else root / ".ingest-manifest.jsonl"
    prior = _load_manifest(manifest_path)

    if args.local:
        local = (os.environ.get("LOCAL_DATABASE_URL") or "").strip()
        if local:
            os.environ["DATABASE_URL"] = local
        from app import create_app

        app = create_app()
    else:
        app = None
        if args.execute and not args.api_key:
            print("Set CM_API_KEY (or pass --api-key) for remote ingest.", file=sys.stderr)
            return 2

    planned: list[dict[str, Any]] = []
    for path in _iter_files(root):
        item = _plan_item(path, root, args)
        prev = prior.get(item["path"])
        if prev and prev.get("status") in _DONE:
            item["status"] = "skipped"
            item["error"] = f"already {prev.get('status')}"
        planned.append(item)
        if args.limit and len([p for p in planned if p.get("status") != "skipped"]) >= args.limit:
            break

    todo = [p for p in planned if p.get("status") == "planned"]
    counts = {
        "root": str(root),
        "dry_run": not args.execute,
        "planned": len(planned),
        "queued": len(todo),
        "created": 0,
        "duplicate": 0,
        "skipped": sum(1 for p in planned if p.get("status") == "skipped"),
        "errors": 0,
    }

    if not args.execute:
        print(
            json.dumps(
                {**counts, "items": planned[:80], "manifest": str(manifest_path)},
                indent=2,
            )
        )
        return 0

    results: list[dict[str, Any]] = []
    paths = {str(p.relative_to(root)).replace("\\", "/"): p for p in _iter_files(root)}

    def run_one(item: dict[str, Any]) -> dict[str, Any]:
        path = paths[item["path"]]
        if args.local:
            assert app is not None
            with app.app_context():
                return _ingest_local(path, item, args)
        import httpx

        with httpx.Client(follow_redirects=True) as client:
            return _ingest_remote(path, item, args, client)

    workers = 1 if args.local else args.workers
    if workers == 1:
        for item in todo:
            result = run_one(item)
            results.append(result)
            _append_manifest(manifest_path, result)
            key = "errors" if result["status"] == "error" else result["status"]
            counts[key] = counts.get(key, 0) + 1
            print(
                f"[{len(results)}/{len(todo)}] {result['status']:9} {result['path']}"
                + (f"  {result.get('error')}" if result.get("error") else ""),
                flush=True,
            )
    else:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(run_one, item): item for item in todo}
            for fut in as_completed(futures):
                result = fut.result()
                results.append(result)
                _append_manifest(manifest_path, result)
                key = "errors" if result["status"] == "error" else result["status"]
                counts[key] = counts.get(key, 0) + 1
                print(
                    f"[{len(results)}/{len(todo)}] {result['status']:9} {result['path']}"
                    + (f"  {result.get('error')}" if result.get("error") else ""),
                    flush=True,
                )

    errors = [r for r in results if r.get("status") == "error"]
    print(
        json.dumps(
            {
                **counts,
                "errors": len(errors),
                "failed": [{"path": e["path"], "error": e.get("error")} for e in errors[:80]],
                "manifest": str(manifest_path),
            },
            indent=2,
        )
    )
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
