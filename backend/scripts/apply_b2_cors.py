"""Set Backblaze B2 CORS so the website can POST PDFs to a one-shot upload URL.

Usage (from backend/, with B2_* in .env or the environment):
    python scripts/apply_b2_cors.py
    python scripts/apply_b2_cors.py --dry-run
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

load_dotenv(_BACKEND / ".env", override=True)

from app.services.object_storage import browser_cors_rules

DEFAULT_ORIGINS = (
    "https://www.usiscm.com",
    "https://usiscm.onrender.com",
)


def _http_json(req: Request) -> dict:
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")[:400]
        raise SystemExit(f"B2 HTTP {exc.code}: {raw}") from exc


def _authorize() -> dict:
    key_id = (os.environ.get("B2_APPLICATION_KEY_ID") or "").strip()
    secret = (os.environ.get("B2_APPLICATION_KEY") or "").strip()
    if not key_id or not secret:
        raise SystemExit("B2_APPLICATION_KEY_ID and B2_APPLICATION_KEY must be set.")
    token = base64.b64encode(f"{key_id}:{secret}".encode()).decode()
    req = Request(
        "https://api.backblazeb2.com/b2api/v2/b2_authorize_account",
        headers={"Authorization": f"Basic {token}"},
        method="GET",
    )
    return _http_json(req)


def _bucket_id(auth: dict, want: str) -> str:
    allowed = auth.get("allowed") or {}
    bucket_id = (allowed.get("bucketId") or "").strip()
    if bucket_id:
        return bucket_id
    body = json.dumps({"accountId": auth.get("accountId")}).encode()
    req = Request(
        f"{auth['apiUrl']}/b2api/v2/b2_list_buckets",
        data=body,
        headers={
            "Authorization": auth["authorizationToken"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    payload = _http_json(req)
    for bucket in payload.get("buckets") or []:
        if bucket.get("bucketName") == want:
            return str(bucket.get("bucketId") or "")
    raise SystemExit(f"Bucket not found for this application key: {want}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--origin",
        action="append",
        dest="origins",
        help="Allowed origin (repeatable). Defaults to usiscm.com and the Render URL.",
    )
    args = parser.parse_args()

    bucket = (os.environ.get("B2_BUCKET_NAME") or "").strip()
    if not bucket:
        raise SystemExit("B2_BUCKET_NAME must be set.")
    origins = [o.strip() for o in (args.origins or list(DEFAULT_ORIGINS)) if o and o.strip()]
    if not origins:
        raise SystemExit("At least one --origin is required.")

    rules = browser_cors_rules(origins)
    print(f"Bucket: {bucket}")
    print(json.dumps(rules, indent=2))
    if args.dry_run:
        print("Dry run — not written.")
        return 0

    auth = _authorize()
    body = json.dumps(
        {
            "accountId": auth.get("accountId"),
            "bucketId": _bucket_id(auth, bucket),
            "corsRules": rules,
        }
    ).encode()
    req = Request(
        f"{auth['apiUrl']}/b2api/v2/b2_update_bucket",
        data=body,
        headers={
            "Authorization": auth["authorizationToken"],
            "Content-Type": "application/json",
        },
        method="POST",
    )
    result = _http_json(req)
    print("Updated CORS rules:")
    print(json.dumps(result.get("corsRules") or rules, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
