"""Parse and upsert AGC San Diego weekly project listing CSVs and HTML."""
from __future__ import annotations

import csv
import html as html_lib
import io
import re
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models.golden_state_planroom_lead import GoldenStatePlanroomLead

_DATA_START_HINTS = ("plan #", "project name")
_OPS_HOST_PREFIX = "https://login.onlineplanservice.com/"
_NAV_URL_RE = re.compile(
    r"""ASPx\.xr_NavigateUrl\('(?P<url>https?://[^'"]+?)(?:&#39;|')""",
    re.I,
)
_NOBR_RE = re.compile(r"<nobr>(.*?)</nobr>", re.I | re.S)
_PLAN_RE = re.compile(r"^\d{2}-\d{5}$")
_WS_RE = re.compile(r"\s+")


def _blank(s: str | None) -> str | None:
    if s is None:
        return None
    stripped = s.strip()
    return None if stripped == "" else stripped


def _parse_money(raw: str | None) -> Decimal | None:
    s = _blank(raw)
    if s is None:
        return None
    cleaned = s.replace("$", "").replace(",", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _parse_date(raw: str | None) -> date | None:
    s = _blank(raw)
    if s is None:
        return None
    for fmt in ("%m/%d/%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_int(raw: str | None) -> int:
    s = _blank(raw)
    if s is None:
        return 0
    try:
        return int(s)
    except ValueError:
        return 0


def _listing_week(rows: list[list[str]]) -> date | None:
    for row in rows[:8]:
        for cell in row:
            parsed = _parse_date(cell)
            if parsed and parsed.year >= 2020:
                return parsed
    return None


def _header_index(rows: list[list[str]]) -> int:
    for i, row in enumerate(rows):
        joined = ",".join(row).lower()
        if all(hint in joined for hint in _DATA_START_HINTS):
            return i
    return 6


def parse_agcs_weekly_csv(text: str) -> tuple[list[dict[str, Any]], date | None]:
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    header_idx = _header_index(rows)
    listing_week = _listing_week(rows)
    projects: list[dict[str, Any]] = []
    for raw in rows[header_idx + 1 :]:
        if len(raw) < 12:
            continue
        plan = _blank(raw[9] if len(raw) > 9 else None)
        name = _blank(raw[11] if len(raw) > 11 else None)
        if not plan or not name:
            continue
        flag = (_blank(raw[0]) or "").upper()
        star = _blank(raw[1]) or ""
        projects.append(
            {
                "plan_number": plan,
                "name": name,
                "location": _blank(raw[6] if len(raw) > 6 else None),
                "bid_date": _parse_date(raw[3] if len(raw) > 3 else None),
                "bid_time": _blank(raw[5] if len(raw) > 5 else None),
                "addenda_count": _parse_int(raw[8] if len(raw) > 8 else None),
                "estimate_high": _parse_money(raw[15] if len(raw) > 15 else None),
                "is_new": flag == "NEW",
                "bid_date_changed": star == "*",
                "listing_week": listing_week,
                "raw_row": {str(i): _blank(c) for i, c in enumerate(raw) if _blank(c)},
            }
        )
    return projects, listing_week


def _decode_cell(text: str) -> str:
    cleaned = html_lib.unescape(text).replace("\xa0", " ").replace("&nbsp;", " ")
    return _WS_RE.sub(" ", cleaned).strip()


def _nobr_texts(chunk: str) -> list[str]:
    out: list[str] = []
    for raw in _NOBR_RE.findall(chunk):
        decoded = _decode_cell(raw)
        if decoded:
            out.append(decoded)
    return out


def _safe_project_url(raw: str | None) -> str | None:
    s = _blank(raw)
    if s is None:
        return None
    decoded = html_lib.unescape(s).strip()
    if not decoded.lower().startswith(_OPS_HOST_PREFIX):
        return None
    if any(ch in decoded for ch in (" ", "\n", "\r", "<", ">", '"', "'")):
        return None
    return decoded[:500]


def _looks_like_html(text: str) -> bool:
    head = text.lstrip()[:800].lower()
    return head.startswith("<!doctype") or "<html" in head or "aspx.xr_navigateurl" in head


def _listing_week_from_html(text: str) -> date | None:
    lowered = text.lower()
    idx = lowered.find("weekly")
    window = text[idx : idx + 5000] if idx >= 0 else text[:40000]
    for nobr in _nobr_texts(window):
        for fmt in ("%B %d, %Y", "%b %d, %Y"):
            try:
                parsed = datetime.strptime(nobr, fmt).date()
            except ValueError:
                continue
            if parsed.year >= 2020:
                return parsed
    return None


def parse_agcs_weekly_html(text: str) -> tuple[list[dict[str, Any]], date | None]:
    listing_week = _listing_week_from_html(text)
    projects: list[dict[str, Any]] = []
    for match in _NAV_URL_RE.finditer(text):
        url = _safe_project_url(match.group("url"))
        if not url:
            continue
        td_open = text.rfind("<td", 0, match.start())
        if td_open < 0:
            continue
        gt = text.find(">", match.start())
        td_close = text.find("</td>", gt if gt >= 0 else match.end())
        if gt < 0 or td_close < 0:
            continue
        name = _decode_cell(" ".join(_nobr_texts(text[gt + 1 : td_close])))
        if not name:
            continue
        tr_start = text.rfind("<tr", 0, td_open)
        before = _nobr_texts(text[tr_start:td_open] if tr_start >= 0 else "")
        after = _nobr_texts(text[td_close : text.find("</tr>", td_close)])
        plan = next((cell for cell in reversed(before) if _PLAN_RE.match(cell)), None)
        if not plan:
            qs = parse_qs(urlparse(url).query)
            plan = _blank((qs.get("bxup") or [None])[0])
        if not plan:
            continue
        date_cell = next((cell for cell in before if _parse_date(cell) and "/" in cell), None)
        time_cell = next((cell for cell in before if "M" in cell.upper() and ":" in cell), None)
        location = next(
            (
                cell
                for cell in before
                if cell.upper() not in {"NEW", "*"}
                and not _PLAN_RE.match(cell)
                and not _parse_date(cell)
                and cell != time_cell
                and not cell.isdigit()
            ),
            None,
        )
        addenda_cell = next((cell for cell in reversed(before) if cell.isdigit()), None)
        estimate_cell = next((cell for cell in after if cell.startswith("$")), None)
        projects.append(
            {
                "plan_number": plan,
                "name": name,
                "location": location,
                "bid_date": _parse_date(date_cell),
                "bid_time": time_cell,
                "addenda_count": _parse_int(addenda_cell),
                "estimate_high": _parse_money(estimate_cell),
                "is_new": any(cell.upper() == "NEW" for cell in before),
                "bid_date_changed": any(cell == "*" for cell in before),
                "listing_week": listing_week,
                "project_url": url,
                "raw_row": {"project_url": url, "name": name, "plan_number": plan},
            }
        )
    return projects, listing_week


def parse_agcs_weekly_listing(
    text: str,
    *,
    filename: str | None = None,
) -> tuple[list[dict[str, Any]], date | None]:
    name = (filename or "").lower()
    if name.endswith((".html", ".htm")) or _looks_like_html(text):
        return parse_agcs_weekly_html(text)
    return parse_agcs_weekly_csv(text)


def _flush_upsert(sess: Session, batch: list[dict[str, Any]]) -> None:
    if not batch:
        return
    table = GoldenStatePlanroomLead.__table__
    ins = pg_insert(table).values(batch)
    update_cols = [
        "name",
        "location",
        "bid_date",
        "bid_time",
        "addenda_count",
        "estimate_high",
        "is_new",
        "bid_date_changed",
        "listing_week",
        "source_file",
        "source",
        "raw_row",
        "updated_at",
    ]
    set_ = {name: func.now() if name == "updated_at" else getattr(ins.excluded, name) for name in update_cols}
    set_["project_url"] = func.coalesce(ins.excluded.project_url, table.c.project_url)
    sess.execute(ins.on_conflict_do_update(index_elements=["plan_number"], set_=set_))
    sess.commit()


def upsert_planroom_rows(
    sess: Session,
    rows: Iterable[dict[str, Any]],
    *,
    source_file: str | None = None,
    batch_size: int = 400,
) -> tuple[int, int]:
    """Upsert parsed weekly rows. Returns ``(loaded, skipped)``."""
    loaded = 0
    skipped = 0
    parsed = 0
    by_plan: dict[str, dict[str, Any]] = {}
    for row in rows:
        plan = _blank(str(row.get("plan_number") or ""))
        name = _blank(str(row.get("name") or ""))
        if not plan or not name:
            skipped += 1
            continue
        parsed += 1
        by_plan[plan] = {
            "plan_number": plan,
            "name": name,
            "location": row.get("location"),
            "bid_date": row.get("bid_date"),
            "bid_time": row.get("bid_time"),
            "addenda_count": int(row.get("addenda_count") or 0),
            "estimate_high": row.get("estimate_high"),
            "is_new": bool(row.get("is_new")),
            "bid_date_changed": bool(row.get("bid_date_changed")),
            "listing_week": row.get("listing_week"),
            "source_file": source_file,
            "source": "ONLINE_PLAN_SERVICE",
            "project_url": _safe_project_url(row.get("project_url") if isinstance(row.get("project_url"), str) else None),
            "raw_row": row.get("raw_row"),
        }
    batch: list[dict[str, Any]] = []
    for payload in by_plan.values():
        batch.append(payload)
        if len(batch) >= batch_size:
            _flush_upsert(sess, batch)
            loaded += len(batch)
            batch.clear()
    if batch:
        _flush_upsert(sess, batch)
        loaded += len(batch)
    skipped += parsed - len(by_plan)
    return loaded, skipped


def load_agcs_weekly_csv(
    sess: Session,
    csv_path: str | Path,
    *,
    source_file: str | None = None,
) -> tuple[int, int, date | None]:
    path = Path(csv_path)
    text = path.read_text(encoding="utf-8-sig", errors="replace")
    rows, listing_week = parse_agcs_weekly_listing(text, filename=path.name)
    loaded, skipped = upsert_planroom_rows(sess, rows, source_file=source_file or path.name)
    return loaded, skipped, listing_week
