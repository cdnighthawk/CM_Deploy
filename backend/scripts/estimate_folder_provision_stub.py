#!/usr/bin/env python3
"""Local HTTP stub for ``ESTIMATE_FOLDER_PROVISION_URL`` (dev / tests).

Implements the data-server contract in docs/estimate-folder-provision.md:

    POST /provision/estimate-folder
    Aliases: /provision/estimate-folders, /estimate-folder
    Header: X-USIS-Provision-Token
    Body: { estimate_id, job_number, name, project_uuid?, requested_by? }
    Response: { ok, path, created }

Example:

    python scripts/estimate_folder_provision_stub.py --root /tmp/usis-estimate-folders --token dev-token
    export ESTIMATE_FOLDER_PROVISION_URL=http://127.0.0.1:8741
    export ESTIMATE_FOLDER_PROVISION_TOKEN=dev-token
"""
from __future__ import annotations

import argparse
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services.estimate_folder_provision import (  # noqa: E402
    PROVISION_HEADER,
    PROVISION_PATH_ALIASES,
    create_local_folder_tree,
    estimate_folder_name,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Local estimate-folder provision agent stub")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8741)
    parser.add_argument("--root", required=True, help="Writable directory that stands in for the file store")
    parser.add_argument("--token", default="dev-token", help="Shared secret for X-USIS-Provision-Token")
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *log_args) -> None:
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % log_args))

        def _json(self, code: int, payload: dict) -> None:
            raw = json.dumps(payload).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self) -> None:  # noqa: N802
            path = (self.path or "").split("?", 1)[0].rstrip("/") or "/"
            if path not in PROVISION_PATH_ALIASES:
                self._json(404, {"ok": False, "error": "not found"})
                return
            got = (self.headers.get(PROVISION_HEADER) or "").strip()
            if args.token and got != args.token:
                self._json(401, {"ok": False, "error": "invalid provision token"})
                return
            length = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._json(400, {"ok": False, "error": "invalid JSON"})
                return
            if not isinstance(body, dict) or not body.get("estimate_id"):
                self._json(400, {"ok": False, "error": "estimate_id is required"})
                return
            folder = body.get("folder_name") or estimate_folder_name(
                body.get("job_number"),
                body.get("name"),
                estimate_id=body.get("estimate_id"),
            )
            try:
                dest, created = create_local_folder_tree(root, str(folder))
            except OSError as exc:
                self._json(500, {"ok": False, "error": str(exc)})
                return
            self._json(200, {"ok": True, "path": dest, "created": created})

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"estimate-folder stub on http://{args.host}:{args.port} root={root}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
