"""Append ``ActiveProjectExternalId`` to Corecon transaction-detail CSV exports.

The value matches ``active project.csv`` column ``id`` and ``lead_estimates.external_id``
after import, so every PO / bill / CO / invoice line carries the same join key.

Usage from the ``backend`` directory::

    python scripts/enrich_corecon_csv_with_active_project.py --dir "E:\\...\\Database files"
    python scripts/enrich_corecon_csv_with_active_project.py --csv "E:\\...\\export.csv" --in-place
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import tempfile
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = THIS_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.corecon_ids import stable_active_project_external_id  # noqa: E402

DEFAULT_DIR = (
    r"E:\OneDrive - godocon.com\New Company Software\Database files"
)
GLOB = "corecon_transactiondetailsapi_export*.csv"


def _to_int(raw: str | None) -> int | None:
    s = (raw or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        try:
            return int(float(s))
        except ValueError:
            return None


def enrich_file(path: Path, *, in_place: bool) -> tuple[int, str]:
    with path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            return 0, "skip: no header"
        fields = list(reader.fieldnames)
        if "ActiveProjectExternalId" not in fields:
            fields.append("ActiveProjectExternalId")
        rows: list[dict[str, str]] = []
        for row in reader:
            pid = _to_int(row.get("ProjectId"))
            pnum = row.get("ProjectNumber")
            ext = stable_active_project_external_id(project_corecon_id=pid, project_number=pnum)
            out = {**row, "ActiveProjectExternalId": ext or ""}
            rows.append(out)

    out_path = path.with_name(path.stem + "_enriched" + path.suffix) if not in_place else path

    fd, tmp_name = tempfile.mkstemp(prefix="corecon-enrich-", suffix=".csv", dir=path.parent)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        with tmp_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k, "") for k in fields})
        if in_place:
            os.replace(tmp_path, path)
            dest = str(path)
        else:
            if out_path.exists():
                out_path.unlink()
            os.replace(tmp_path, out_path)
            dest = str(out_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise

    return len(rows), dest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=DEFAULT_DIR, help="Directory to glob for CSV files")
    parser.add_argument("--csv", action="append", default=[], help="Explicit file (repeatable)")
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite each input file (default without --csv: in-place on glob matches)",
    )
    args = parser.parse_args()

    if args.csv:
        paths = [Path(p) for p in args.csv]
        in_place = args.in_place
    else:
        paths = sorted(Path(args.dir).glob(GLOB))
        in_place = True

    paths = [p for p in paths if p.is_file()]
    if not paths:
        print(f"No files matched.", file=sys.stderr)
        return 2

    total = 0
    for p in paths:
        if "active project" in p.name.lower():
            continue
        n, dest = enrich_file(p, in_place=in_place)
        print(f"{p.name} -> {n} rows, wrote {dest}")
        total += n
    print(f"Done. {len(paths)} file(s), {total} row(s) total.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
