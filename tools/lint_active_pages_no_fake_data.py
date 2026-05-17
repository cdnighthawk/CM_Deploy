#!/usr/bin/env python3
"""Fail if active USIS pages contain known W3CRM template filler strings.

Uses ``tools/usis-active-pages-checklist.json``. Template pages (Plan 20 §C) are not scanned.

  python tools/lint_active_pages_no_fake_data.py
  python tools/lint_active_pages_no_fake_data.py --dist   # also check gulp/dist after build
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GULP_SRC = REPO / "W3CRM-v3.0-13_September_2025" / "gulp" / "src"
GULP_DIST = REPO / "W3CRM-v3.0-13_September_2025" / "gulp" / "dist"
CHECKLIST = REPO / "tools" / "usis-active-pages-checklist.json"


def load_checklist() -> tuple[list[str], list[str], list[str]]:
    data = json.loads(CHECKLIST.read_text(encoding="utf-8"))
    pages = [p["path"] for p in data.get("pages", [])]
    partials = list(data.get("shared_partials", []))
    patterns = list(data.get("deny_list_patterns", []))
    return pages, partials, patterns


def scan_file(path: Path, patterns: list[str]) -> list[tuple[str, int, str]]:
    if not path.is_file():
        return [("__missing__", 0, str(path))]
    text = path.read_text(encoding="utf-8", errors="replace")
    hits: list[tuple[str, int, str]] = []
    for pat in patterns:
        if pat not in text:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            if pat in line:
                hits.append((pat, i, line.strip()[:120]))
    return hits


def scan_root(root: Path, rel_paths: list[str], patterns: list[str]) -> int:
    failures = 0
    for rel in rel_paths:
        hits = scan_file(root / rel, patterns)
        if not hits:
            continue
        failures += len(hits)
        print(f"\n{rel}:")
        for pat, line_no, snippet in hits:
            if pat == "__missing__":
                print(f"  MISSING FILE: {snippet}")
            else:
                print(f"  L{line_no}: [{pat}] {snippet}")
    return failures


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dist", action="store_true", help="Also scan gulp/dist")
    args = parser.parse_args()

    pages, partials, patterns = load_checklist()
    total = scan_root(GULP_SRC, pages + partials, patterns)
    if args.dist:
        # Partials are inlined into built HTML; scan compiled pages only.
        total += scan_root(GULP_DIST, pages, patterns)

    if total:
        print(f"\n{total} deny-list hit(s) on active pages. See tools/usis-active-pages-checklist.json.")
        return 1
    print("OK: no deny-list strings on active pages or shared construction partials.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
