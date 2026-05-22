#!/usr/bin/env python3
"""Verify Backblaze B2 credentials and bucket access from backend/.env.

Usage (from backend/):
    python scripts/verify_b2_storage.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

load_dotenv(_BACKEND_DIR / ".env", override=True)


def main() -> int:
    from app import create_app
    from app.services.object_storage import UploadCategory, b2_enabled, object_key

    app = create_app()
    with app.app_context():
        if not b2_enabled():
            print("B2 is NOT enabled.")
            print("Set all four required vars in backend/.env:")
            print("  B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_ENDPOINT")
            return 1

        cfg = app.config
        bucket = cfg["B2_BUCKET_NAME"]
        endpoint = cfg["B2_ENDPOINT"]
        prefix = (cfg.get("B2_PREFIX") or "").strip() or "(none)"
        key_id = str(cfg["B2_APPLICATION_KEY_ID"] or "")
        print(f"B2 enabled — bucket={bucket!r} endpoint={endpoint!r} prefix={prefix!r}")
        print(f"Key ID: {key_id[:6]}…{key_id[-4:]}" if len(key_id) > 10 else f"Key ID: {key_id}")

        from app.services.object_storage import _s3_client  # noqa: PLC2701

        client = _s3_client()
        try:
            client.head_bucket(Bucket=bucket)
            print("head_bucket: OK")
        except Exception as exc:
            print(f"head_bucket FAILED: {exc}")
            print("Check keyID vs applicationKey, bucket name, and S3 endpoint region.")
            return 2

        probe_key = object_key(UploadCategory.HR_I9, ".usis-b2-probe")
        try:
            client.put_object(Bucket=bucket, Key=probe_key, Body=b"ok", ContentType="text/plain")
            client.delete_object(Bucket=bucket, Key=probe_key)
            print(f"write/delete probe object OK ({probe_key})")
        except Exception as exc:
            print(f"write probe FAILED: {exc}")
            print("Key may lack writeFiles/deleteFiles on this bucket.")
            return 3

        print("Backblaze B2 is configured correctly. New uploads will go to B2.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
