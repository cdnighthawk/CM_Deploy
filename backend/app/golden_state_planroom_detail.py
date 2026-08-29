"""Parse Online Plan Service project-detail HTML into a stored payload."""
from __future__ import annotations

import html as html_lib
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models.golden_state_planroom_lead import GoldenStatePlanroomLead

_CAPTION_RE = re.compile(
    r'class="[^"]*project-caption[^"]*"[^>]*>(?P<label>.*?)</(?:div|span|td|th)>'
    r"\s*<[^>]+>(?P<value>.*?)</(?:div|span|td|th|p)>",
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_KEY_MAP = {
    "status": "status",
    "bin #": "bin_number",
    "postponed": "postponed",
    "bid time": "bid_time",
    "street": "street",
    "city": "city",
    "county": "county",
    "zip code": "zip",
    "project type": "project_type",
    "bid packages": "bid_packages",
    "estimate low": "estimate_low",
    "estimate high": "estimate_high",
    "contract#/ref": "contract_ref",
    "published date": "published_date",
    "plan status": "plan_status",
    "spec status": "spec_status",
    "no of plans": "no_of_plans",
    "no of specs": "no_of_specs",
    "plans cost": "plans_cost",
    "description": "description",
    "pre bid": "pre_bid",
    "pre bid conference": "pre_bid",
}


def _clean(raw: str | None) -> str:
    text = html_lib.unescape(_TAG_RE.sub(" ", raw or ""))
    return _WS_RE.sub(" ", text.replace("\xa0", " ")).strip(" :")


def parse_ops_detail_html(html: str) -> dict[str, Any] | None:
    if not html:
        return None
    head = html[:4000].lower()
    if "plan room login" in head and "project-caption" not in html.lower():
        return None
    payload: dict[str, Any] = {}
    for match in _CAPTION_RE.finditer(html):
        label = _clean(match.group("label")).lower()
        value = _clean(match.group("value"))
        key = _KEY_MAP.get(label)
        if not key or not value:
            continue
        if key in payload and payload[key]:
            continue
        payload[key] = value
    if not payload:
        return None
    if payload.get("postponed"):
        payload["postponed"] = payload["postponed"].lower().startswith("y")
    return payload


def apply_detail_updates(
    sess: Session,
    items: list[dict[str, Any]],
) -> tuple[int, int]:
    updated = 0
    skipped = 0
    now = datetime.now(tz=timezone.utc)
    for item in items:
        plan = str(item.get("plan_number") or "").strip()
        detail = item.get("detail")
        if not plan or not isinstance(detail, dict) or not detail:
            skipped += 1
            continue
        row = sess.scalar(select(GoldenStatePlanroomLead).where(GoldenStatePlanroomLead.plan_number == plan))
        if row is None:
            skipped += 1
            continue
        row.detail = detail
        row.details_fetched_at = now
        updated += 1
    if updated:
        sess.commit()
    return updated, skipped
