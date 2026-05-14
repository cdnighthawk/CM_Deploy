"""Split grouped company/contact CSV and optionally merge HubSpot export.

**Grouped file** (``Companies_*_Grouped by Company.csv``): company row has
``lblCompanyNamePhone`` filled; following rows are contacts until the next company.

**HubSpot** (optional): ``--hubspot`` adds/replaces contacts. On duplicate keys
(normalized email, else phone digits, else name+company bucket), **HubSpot
wins** over the grouped export.

Outputs
-------
Without ``--hubspot``::

    {input_stem}_companies.csv
    {input_stem}_contacts.csv

With ``--hubspot`` (merged; HubSpot de-duplicated last-wins within HubSpot)::

    Companies_Companies_Contacts_merged_companies.csv
    Companies_Companies_Contacts_merged_contacts.csv

Usage::

    python scripts/split_grouped_companies_contacts_csv.py
    python scripts/split_grouped_companies_contacts_csv.py --hubspot
    python scripts/split_grouped_companies_contacts_csv.py --hubspot "D:\\path\\hubspot.csv"
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = THIS_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

DEFAULT_INPUT = (
    r"E:\OneDrive - godocon.com\New Company Software\Database files"
    r"\Companies_Companies_Contacts Grouped by Company.csv"
)
DEFAULT_HUBSPOT = (
    r"E:\OneDrive - godocon.com\New Company Software\Database files"
    r"\hubspot-crm-exports-all-contacts-2026-04-09.csv"
)
MERGED_STEM = "Companies_Companies_Contacts_merged"


def _clean(s: str | None) -> str:
    if s is None:
        return ""
    return str(s).replace("\ufeff", "").strip()


def _split_display_name(display: str) -> tuple[str, str]:
    parts = display.split()
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


_WS = re.compile(r"\s+")


def _norm_company_name(raw: str) -> str:
    s = _clean(raw)
    s = _WS.sub(" ", s)
    return s


def _norm_company_key(name: str) -> str:
    return _WS.sub(" ", _clean(name).lower())


def _digits_phone(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")


def contact_dedupe_key(row: dict[str, str]) -> str:
    """Stable key for de-duplication (HubSpot overwrites grouped on match)."""
    email = (row.get("email") or "").strip().lower()
    if email:
        return f"e:{email}"
    p = _digits_phone(row.get("businessPhone") or "") or _digits_phone(row.get("mobile") or "")
    if len(p) >= 10:
        return f"p:{p}"
    fn = (row.get("firstName") or "").strip().lower()
    ln = (row.get("lastName") or "").strip().lower()
    cid = (row.get("importCompanyId") or "").strip()
    cn = (row.get("companyName") or "").strip().lower()
    disp = (row.get("contactDisplayName") or "").strip().lower()
    return f"n:{cid}:{fn}:{ln}:{cn}:{disp}"


def parse_grouped(src: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    companies: list[dict[str, str]] = []
    contacts: list[dict[str, str]] = []
    current_id: int | None = None
    current_name = ""

    with src.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV has no header row.")
        keys = list(reader.fieldnames)
        norm_map = {_clean(k).lower(): k for k in keys}

        def col(*aliases: str) -> str:
            for a in aliases:
                k = norm_map.get(a.lower())
                if k:
                    return k
            return aliases[0]

        c_lbl = col("lblCompanyNamePhone")
        c_disp = col("ContactDisplayName")
        c_title = col("ContactTitle")
        c_city = col("ContactBusinessCity")
        c_state = col("ContactBusinessState")
        c_bphone = col("ContactBusinessPhone")
        c_mobile = col("ContactMobile")
        c_email = col("ContactEmail")

        for row in reader:
            lbl = _norm_company_name(row.get(c_lbl, "") or "")
            disp = _clean(row.get(c_disp, "") or "")

            if lbl and not disp:
                cid = len(companies) + 1
                current_id = cid
                current_name = lbl
                companies.append({"importCompanyId": str(cid), "name": lbl})
                continue

            if disp:
                if current_id is None:
                    continue
                fn, ln = _split_display_name(disp)
                contacts.append(
                    {
                        "importCompanyId": str(current_id),
                        "companyName": current_name,
                        "contactDisplayName": disp,
                        "firstName": fn,
                        "lastName": ln,
                        "title": _clean(row.get(c_title, "") or ""),
                        "businessCity": _clean(row.get(c_city, "") or ""),
                        "businessState": _clean(row.get(c_state, "") or ""),
                        "businessPhone": _clean(row.get(c_bphone, "") or ""),
                        "mobile": _clean(row.get(c_mobile, "") or ""),
                        "email": _clean(row.get(c_email, "") or ""),
                    }
                )

    return companies, contacts


def merge_hubspot(
    companies: list[dict[str, str]],
    contacts: list[dict[str, str]],
    hubspot_path: Path,
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """Return new companies list and merged contact list (HubSpot wins on key collision)."""
    name_to_id: dict[str, int] = {}
    for c in companies:
        k = _norm_company_key(c["name"])
        name_to_id[k] = int(c["importCompanyId"])

    mx = max((int(c["importCompanyId"]) for c in companies), default=0)
    next_id = mx + 1
    UNKNOWN = "(imported — no company in HubSpot)"

    def ensure_company_id(raw_name: str) -> int:
        nonlocal next_id
        name = _norm_company_name(raw_name) if raw_name.strip() else UNKNOWN
        key = _norm_company_key(name)
        if key in name_to_id:
            return name_to_id[key]
        nid = next_id
        next_id = nid + 1
        name_to_id[key] = nid
        companies.append({"importCompanyId": str(nid), "name": name})
        return nid

    # Ordered: grouped first, then HubSpot rows (later HubSpot row wins vs earlier HubSpot)
    by_key: dict[str, dict[str, str]] = {}
    for row in contacts:
        by_key[contact_dedupe_key(row)] = dict(row)

    with hubspot_path.open(newline="", encoding="utf-8-sig", errors="replace") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("HubSpot CSV has no header.")
        nm = {_clean(h).lower(): h for h in reader.fieldnames}

        def hc(*aliases: str) -> str:
            for a in aliases:
                if a.lower() in nm:
                    return nm[a.lower()]
            return aliases[0]

        k_fn = hc("First Name")
        k_ln = hc("Last Name")
        k_em = hc("Email")
        k_ph = hc("Phone Number")
        k_co = hc("Company Name")
        k_ls = hc("Lead Status")

        for row in reader:
            fn = _clean(row.get(k_fn, "") or "")
            ln = _clean(row.get(k_ln, "") or "")
            if not fn and not ln and not (row.get(k_em, "") or "").strip():
                continue
            cname_raw = _clean(row.get(k_co, "") or "")
            cid = ensure_company_id(cname_raw if cname_raw else UNKNOWN)
            cname = next(c["name"] for c in companies if int(c["importCompanyId"]) == cid)
            phone = _clean(row.get(k_ph, "") or "")
            email = _clean(row.get(k_em, "") or "")
            lead = _clean(row.get(k_ls, "") or "")
            display = f"{fn} {ln}".strip() or email or phone
            hub_row = {
                "importCompanyId": str(cid),
                "companyName": cname,
                "contactDisplayName": display,
                "firstName": fn,
                "lastName": ln,
                "title": lead,
                "businessCity": "",
                "businessState": "",
                "businessPhone": phone,
                "mobile": "",
                "email": email,
            }
            by_key[contact_dedupe_key(hub_row)] = hub_row

    merged_contacts = sorted(
        by_key.values(),
        key=lambda r: (int(r["importCompanyId"]), (r["lastName"] or "").lower(), (r["firstName"] or "").lower()),
    )
    companies_out = sorted(companies, key=lambda c: int(c["importCompanyId"]))
    return companies_out, merged_contacts


CONTACT_FIELDS = [
    "importCompanyId",
    "companyName",
    "contactDisplayName",
    "firstName",
    "lastName",
    "title",
    "businessCity",
    "businessState",
    "businessPhone",
    "mobile",
    "email",
]


def write_companies_contacts(
    out_dir: Path,
    stem: str,
    companies: list[dict[str, str]],
    contacts: list[dict[str, str]],
) -> tuple[Path, Path]:
    companies_path = out_dir / f"{stem}_companies.csv"
    contacts_path = out_dir / f"{stem}_contacts.csv"
    with companies_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["importCompanyId", "name"])
        w.writeheader()
        w.writerows(companies)
    with contacts_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CONTACT_FIELDS)
        w.writeheader()
        w.writerows(contacts)
    return companies_path, contacts_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", "-i", default=DEFAULT_INPUT, help="Grouped source CSV path")
    parser.add_argument(
        "--hubspot",
        nargs="?",
        const=DEFAULT_HUBSPOT,
        default=None,
        metavar="PATH",
        help="HubSpot all-contacts export. If flag is used with no path, a default OneDrive file is used.",
    )
    args = parser.parse_args()

    src = Path(args.input)
    if not src.is_file():
        print(f"Input not found: {src}", file=sys.stderr)
        return 2

    companies, contacts = parse_grouped(src)
    out_dir = src.parent

    if args.hubspot is not None:
        hub = Path(args.hubspot)
        if not hub.is_file():
            print(f"HubSpot file not found: {hub}", file=sys.stderr)
            return 2
        companies, contacts = merge_hubspot(companies, contacts, hub)
        stem = MERGED_STEM
        cp, tp = write_companies_contacts(out_dir, stem, companies, contacts)
        print(f"Merged (HubSpot wins on duplicate keys):")
        print(f"  Companies: {len(companies)} -> {cp}")
        print(f"  Contacts:  {len(contacts)} -> {tp}")
        return 0

    stem = src.stem
    cp, tp = write_companies_contacts(out_dir, stem, companies, contacts)
    print(f"Companies: {len(companies)} -> {cp}")
    print(f"Contacts:  {len(contacts)} -> {tp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
