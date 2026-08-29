#!/usr/bin/env python3
"""Copy Backblaze B2 objects onto a local or NAS folder.

Run this on a PC that can see the NAS. Do not set B2_MIRROR_ROOT on Render
(the instance disk is 1 GB).

Usage (from backend/):
    python scripts/mirror_b2.py
    python scripts/mirror_b2.py --dry-run
    python scripts/mirror_b2.py --root "\\\\Usisserver\\usiscm"
    python scripts/mirror_b2.py --copy-source "C:\\Users\\...\\UCMMEB\\A-G-Revisions"
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

load_dotenv(_BACKEND_DIR / ".env", override=True)

UCMEB_SOURCE = Path(r"C:\Users\CharlesDossett\Downloads\UCMMEB\A-G-Revisions")


def _env(*names: str) -> str:
    for name in names:
        val = (os.environ.get(name) or "").strip()
        if val:
            return val
    return ""


def _s3_client(endpoint: str, key_id: str, key: str):
    import boto3

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=key,
        region_name="us-east-1",
    )


def dest_for_key(root: Path, key: str) -> Path:
    parts = [p for p in key.replace("\\", "/").split("/") if p and p not in (".", "..")]
    return root.joinpath(*parts)


def should_skip(dest: Path, size: int) -> bool:
    try:
        return dest.is_file() and dest.stat().st_size == size
    except OSError:
        return False


def copy_tree(src: Path, dest: Path, *, dry_run: bool) -> tuple[int, int, int]:
    """Copy a local folder onto the NAS. Returns (copied, skipped, failed)."""
    copied = skipped = failed = 0
    if not src.is_dir():
        print(f"copy-source missing: {src}")
        return 0, 0, 1
    for path in src.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(src)
        out = dest.joinpath(*rel.parts)
        try:
            sz = path.stat().st_size
            if should_skip(out, sz):
                skipped += 1
                continue
            if dry_run:
                print(f"would copy {rel} ({sz} bytes)")
                copied += 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, out)
            copied += 1
            print(f"copied {rel}")
        except OSError as exc:
            failed += 1
            print(f"FAIL {rel}: {exc}")
    return copied, skipped, failed


def mirror_bucket(
    *,
    root: Path,
    bucket: str,
    endpoint: str,
    key_id: str,
    key: str,
    prefix: str,
    dry_run: bool,
) -> tuple[int, int, int]:
    client = _s3_client(endpoint, key_id, key)
    copied = skipped = failed = 0
    paginator = client.get_paginator("list_objects_v2")
    kwargs: dict = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix if prefix.endswith("/") else prefix + "/"
        # Also include the prefix without trailing slash for exact-key objects.
        kwargs["Prefix"] = prefix.rstrip("/") + "/"

    print(f"listing s3://{bucket}/{kwargs.get('Prefix', '')}")
    for page in paginator.paginate(**kwargs):
        for obj in page.get("Contents") or []:
            key_name = obj.get("Key") or ""
            if not key_name or key_name.endswith("/"):
                continue
            size = int(obj.get("Size") or 0)
            dest = dest_for_key(root, key_name)
            if should_skip(dest, size):
                skipped += 1
                continue
            if dry_run:
                print(f"would fetch {key_name} ({size} bytes)")
                copied += 1
                continue
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                client.download_file(bucket, key_name, str(dest))
                copied += 1
                print(f"fetched {key_name}")
            except Exception as exc:
                failed += 1
                print(f"FAIL {key_name}: {exc}")
    return copied, skipped, failed


def main() -> int:
    parser = argparse.ArgumentParser(description="Mirror B2 objects onto a NAS or local folder.")
    parser.add_argument(
        "--root",
        default="",
        help="Destination root (default: B2_MIRROR_ROOT).",
    )
    parser.add_argument(
        "--copy-source",
        default="",
        help="Also copy a local folder (human-readable) under <root>/UCMEB/<name>.",
    )
    parser.add_argument(
        "--copy-ucmeb",
        action="store_true",
        help=f"Copy {UCMEB_SOURCE} to <root>/UCMEB/A-G-Revisions (no B2 download).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List work without writing files.",
    )
    parser.add_argument(
        "--skip-b2",
        action="store_true",
        help="Only run --copy-source; do not list or download from B2.",
    )
    args = parser.parse_args()

    root_raw = (args.root or _env("B2_MIRROR_ROOT")).strip()
    if not root_raw:
        print("Set B2_MIRROR_ROOT or pass --root (NAS UNC or mapped drive).")
        print("Do not set B2_MIRROR_ROOT on Render.")
        return 1
    root = Path(root_raw)

    copied = skipped = failed = 0

    copy_src = (args.copy_source or "").strip()
    if args.copy_ucmeb and not copy_src:
        copy_src = str(UCMEB_SOURCE)

    if copy_src:
        src = Path(copy_src)
        dest = root / "UCMEB" / src.name
        print(f"copy {src} -> {dest}")
        c, s, f = copy_tree(src, dest, dry_run=args.dry_run)
        copied += c
        skipped += s
        failed += f

    if not args.skip_b2:
        key_id = _env("B2_APPLICATION_KEY_ID")
        secret = _env("B2_APPLICATION_KEY")
        bucket = _env("B2_BUCKET_NAME")
        endpoint = _env("B2_ENDPOINT")
        prefix = _env("B2_PREFIX")
        if not all((key_id, secret, bucket, endpoint)):
            print("B2 is not configured in backend/.env.")
            print("Need B2_APPLICATION_KEY_ID, B2_APPLICATION_KEY, B2_BUCKET_NAME, B2_ENDPOINT.")
            return 2
        c, s, f = mirror_bucket(
            root=root,
            bucket=bucket,
            endpoint=endpoint,
            key_id=key_id,
            key=secret,
            prefix=prefix,
            dry_run=args.dry_run,
        )
        copied += c
        skipped += s
        failed += f

    print(f"done copied={copied} skipped={skipped} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
