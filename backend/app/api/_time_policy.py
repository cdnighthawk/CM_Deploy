"""Company timekeeping policy JSON (amendable, frozen on in-flight periods)."""
from __future__ import annotations

from typing import Any, Mapping

from sqlalchemy import select

from ..extensions import db
from ..models.hrms_core import HrmsModuleSetting

TIMEKEEPING_POLICY_KEY = "timekeeping_policy"

DEFAULT_TIME_POLICY: dict[str, Any] = {
    "timezone": "America/Los_Angeles",
    "week_start": "sunday",
    "ot_daily_hours": 8,
    "dt_daily_hours": 12,
    "ot_weekly_hours": 40,
    "seventh_day_ot": True,
    "meal_after_hours": 5,
    "meal_minutes": 30,
    "second_meal_after_hours": 10,
    "rest_minutes_per_4h": 10,
    "geofence_default_mode": "flag",
    "require_cost_code": False,
    "require_daily_signoff": True,
    "require_supervisor_approve_before_export": True,
    "block_export_with_open_flags": True,
    "open_punch_flag_after_hours": 12,
    "web_punch_allowed": True,
    "breadcrumb_min_interval_sec": 180,
    "track_off_clock": False,
    "show_own_cost_on_my_time": False,
}

WEEKDAY_INDEX = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

FINISH_TRADE_COST_CODES: tuple[tuple[str, str, str, int, bool], ...] = (
    ("09 21 00", "Metal framing / drywall", "drywall", 10, True),
    ("09 29 00", "Gypsum board", "drywall", 20, True),
    ("09 91 00", "Painting", "paint", 30, True),
    ("09 65 00", "Resilient flooring", "flooring", 40, True),
    ("09 51 00", "Acoustical ceilings", "ceilings", 50, True),
    ("10 21 00", "Toilet compartments", "div10", 60, True),
    ("10 51 00", "Lockers", "div10", 70, True),
    ("10 14 00", "Signage", "div10", 80, True),
    ("10 44 00", "Fire extinguisher cabinets", "div10", 90, True),
    ("10 26 00", "Wall protection", "div10", 100, True),
    ("TRAVEL", "Travel", "other", 200, True),
    ("SHOP", "Shop", "other", 210, True),
    ("DUMP", "Dump", "other", 220, True),
    ("WARRANTY", "Warranty", "other", 230, True),
    ("EXTRA", "Extra work", "other", 240, True),
    ("TM", "T&M", "other", 250, True),
)


def merge_policy(raw: Mapping[str, Any] | None) -> dict[str, Any]:
    out = dict(DEFAULT_TIME_POLICY)
    if isinstance(raw, Mapping):
        for key, val in raw.items():
            if key in DEFAULT_TIME_POLICY:
                out[key] = val
    out["require_cost_code"] = bool(out.get("require_cost_code"))
    out["week_start"] = str(out.get("week_start") or "sunday").strip().lower()
    if out["week_start"] not in WEEKDAY_INDEX:
        out["week_start"] = "sunday"
    mode = str(out.get("geofence_default_mode") or "flag").strip().lower()
    out["geofence_default_mode"] = mode if mode in ("flag", "block") else "flag"
    return out


def load_time_policy() -> dict[str, Any]:
    row = db.session.scalar(select(HrmsModuleSetting).where(HrmsModuleSetting.key == TIMEKEEPING_POLICY_KEY))
    raw = row.value if row is not None and isinstance(row.value, dict) else None
    return merge_policy(raw)


def save_time_policy(data: Mapping[str, Any]) -> dict[str, Any]:
    merged = merge_policy({**load_time_policy(), **dict(data)})
    row = db.session.scalar(select(HrmsModuleSetting).where(HrmsModuleSetting.key == TIMEKEEPING_POLICY_KEY))
    if row is None:
        row = HrmsModuleSetting(key=TIMEKEEPING_POLICY_KEY, value=merged)
        db.session.add(row)
    else:
        row.value = merged
        db.session.add(row)
    db.session.flush()
    return merged
