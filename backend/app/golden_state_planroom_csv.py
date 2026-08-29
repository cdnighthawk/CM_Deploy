"""Parse and upsert AGC San Diego weekly project listing CSVs."""
from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from .models.golden_state_planroom_lead import GoldenStatePlanroomLead

_DATA_START_HINTS = ("plan #", "project name")


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
    rows, listing_week = parse_agcs_weekly_csv(text)
    loaded, skipped = upsert_planroom_rows(sess, rows, source_file=source_file or path.name)
    return loaded, skipped, listing_week
