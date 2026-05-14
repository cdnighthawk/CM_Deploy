"""Build a BuildingConnected-shaped CSV of active Corecon jobs for ``lead_estimates`` import.

``scripts/load_lead_estimates.py`` expects the same column names / shapes as a BC
``bc_projects`` export. This script dedupes a Corecon transaction-details CSV by
project and emits one row per job with every BC column present (blank where unknown).

Typical usage::

    python scripts/export_active_projects_bc_csv.py
    python scripts/export_active_projects_bc_csv.py --corecon "path/to/export.csv"
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.corecon_ids import stable_active_project_external_id  # noqa: E402

DEFAULT_BC_TEMPLATE = (
    r"E:\OneDrive - godocon.com\New Company Software\Database files\bc_projects_20260419_161452.csv"
)
DEFAULT_CORECON = (
    r"E:\OneDrive - godocon.com\New Company Software\Database files"
    r"\corecon_transactiondetailsapi_export20260331_123656pm.csv"
)
DEFAULT_OUT = (
    r"E:\OneDrive - godocon.com\New Company Software\Database files\active project.csv"
)

_SENTINEL_DATE_RE = re.compile(r"^\s*01/01/0001\b")


def _blank(s: str | None) -> bool:
    return s is None or str(s).strip() == ""


def _corecon_dt_to_iso_z(raw: str | None) -> str:
    """Parse Corecon export local-style datetimes; return ISO-8601 Z or empty."""
    if _blank(raw) or _SENTINEL_DATE_RE.match(str(raw) or ""):
        return ""
    s = str(raw).strip()
    for fmt in ("%m/%d/%Y %H:%M", "%m/%d/%Y %H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
            return dt.isoformat().replace("+00:00", "Z")
        except ValueError:
            continue
    return ""


def _pick_representative(rows: list[dict[str, str]]) -> dict[str, str]:
    """Prefer an approved prime-contract row so prime metadata is populated."""
    prime = [
        r
        for r in rows
        if (r.get("TransactionSource") or "").strip() == "Prime Contract"
        and (r.get("PrimeContractStatus") or "").strip().lower() == "approved"
    ]
    if prime:
        return prime[0]
    prime_any = [r for r in rows if (r.get("TransactionSource") or "").strip() == "Prime Contract"]
    if prime_any:
        return prime_any[0]
    return rows[0]


def _client_json(row: dict[str, str]) -> str:
    owner = (row.get("OwnerCompanyName") or "").strip()
    prime_co = (row.get("PrimeCompanyName") or "").strip()
    name = owner or prime_co
    payload: dict[str, Any] = {"company": {"name": name} if name else {}}
    return json.dumps(payload, ensure_ascii=False)


def _project_information(row: dict[str, str]) -> str:
    title = (row.get("ProjectTitle") or "").strip()
    num = (row.get("ProjectNumber") or "").strip()
    subj = (row.get("PrimeContractSubject") or "").strip()
    gc = (row.get("PrimeCompanyName") or "").strip()
    owner = (row.get("OwnerCompanyName") or "").strip()
    bits = [
        f"<div><b>Corecon job</b> #{html.escape(num)} — {html.escape(title)}</div>" if title or num else "",
        f"<div>Prime contract: {html.escape(subj)}</div>" if subj else "",
        f"<div>GC: {html.escape(gc)}</div>" if gc else "",
        f"<div>Owner: {html.escape(owner)}</div>" if owner else "",
    ]
    return "".join(b for b in bits if b)


def _external_id(row: dict[str, str]) -> str:
    pid = _to_int(row.get("ProjectId"))
    pnum = (row.get("ProjectNumber") or "").strip()
    ext = stable_active_project_external_id(project_corecon_id=pid, project_number=pnum or None)
    return ext or "corecon-project-unknown"


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


def _group_key(row: dict[str, str]) -> str:
    pid = (row.get("ProjectId") or "").strip()
    pnum = (row.get("ProjectNumber") or "").strip()
    if pid:
        return f"id:{pid}"
    return f"num:{pnum}" if pnum else "unknown"


def _bc_row_from_corecon(template_fields: list[str], rep: dict[str, str]) -> dict[str, str]:
    """One dict keyed exactly like ``bc_projects`` CSV columns."""
    created = _corecon_dt_to_iso_z(rep.get("PrimeContractIssueDateUtc")) or _corecon_dt_to_iso_z(
        rep.get("PrimeContractApprovalDateUtc")
    )
    updated = _corecon_dt_to_iso_z(rep.get("PrimeContractApprovalDateUtc")) or created
    out: dict[str, str] = {k: "" for k in template_fields}
    out["id"] = _external_id(rep)
    out["name"] = (rep.get("ProjectTitle") or "").strip()
    out["number"] = (rep.get("ProjectNumber") or "").strip()
    out["client"] = _client_json(rep)
    out["tradeName"] = (rep.get("PrimeContractSubject") or "").strip()
    out["submissionState"] = ""
    out["outcome"] = json.dumps(
        {"state": "UNKNOWN", "otherReason": None, "updatedAt": None, "updatedBy": None},
        ensure_ascii=False,
    )
    out["dueAt"] = ""
    out["updatedAt"] = updated
    out["createdAt"] = created
    out["isArchived"] = "False"
    out["finalValue"] = ""
    out["additionalInfo"] = ""
    out["architect"] = ""
    out["averageCrewSize"] = ""
    out["bid"] = ""
    out["clientValues"] = ""
    out["competitors"] = ""
    out["contractDuration"] = ""
    out["contractStartAt"] = _corecon_dt_to_iso_z(rep.get("PrimeContractEstStartDateUtc"))
    out["customTags"] = ""
    out["declineReasons"] = ""
    out["defaultCurrency"] = "USD"
    out["engineer"] = ""
    out["estimatingHours"] = ""
    out["expectedFinishAt"] = _corecon_dt_to_iso_z(rep.get("ProjectEstFinishDateUtc"))
    out["expectedStartAt"] = _corecon_dt_to_iso_z(rep.get("ProjectEstStartDateUtc"))
    out["feePercentage"] = ""
    out["followUpAt"] = ""
    out["groupChildren"] = ""
    out["invitedAt"] = ""
    out["isNdaRequired"] = "False"
    out["isParent"] = "False"
    out["isSealedBidding"] = "False"
    out["jobWalkAt"] = ""
    out["location"] = ""
    out["marketSector"] = ""
    out["members"] = "[]"
    out["owningOfficeId"] = ""
    out["parentId"] = ""
    out["priority"] = ""
    out["profitMargin"] = ""
    out["projectInformation"] = _project_information(rep)
    out["projectIsPublic"] = "True"
    out["projectSize"] = ""
    out["propertyOwner"] = ""
    out["propertyTenant"] = ""
    out["requestType"] = ""
    out["rfisDueAt"] = ""
    out["rom"] = ""
    out["source"] = "CORECON"
    out["tradeSpecificInstructions"] = ""
    out["winProbability"] = ""
    out["workflowBucket"] = "ACTIVE_CM"
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template", default=DEFAULT_BC_TEMPLATE, help="BC projects CSV (header row only is required)")
    parser.add_argument("--corecon", default=DEFAULT_CORECON, help="Corecon transaction details export CSV")
    parser.add_argument("--out", default=DEFAULT_OUT, help="Output CSV path")
    args = parser.parse_args()

    template_path = Path(args.template)
    corecon_path = Path(args.corecon)
    out_path = Path(args.out)

    with template_path.open(newline="", encoding="utf-8", errors="replace") as f:
        r = csv.reader(f)
        header = next(r)
    fieldnames = [h for h in header if str(h).strip() != ""]

    groups: dict[str, list[dict[str, str]]] = {}
    with corecon_path.open(newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = _group_key(row)
            if key == "unknown":
                continue
            groups.setdefault(key, []).append(row)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for _key, rows in sorted(groups.items(), key=lambda kv: kv[0]):
            rep = _pick_representative(rows)
            w.writerow(_bc_row_from_corecon(fieldnames, rep))

    print(f"Wrote {len(groups)} rows to {out_path} (columns: {len(fieldnames)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
