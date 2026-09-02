"""California overtime / meal engine. Pure functions — unit-tested, no Flask."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable, Mapping, Sequence

TWOPLACES = Decimal("0.01")
HOUR = Decimal("3600")


def _hours(seconds: float) -> Decimal:
    return (Decimal(str(max(0.0, seconds))) / HOUR).quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def _as_dt(raw: Any) -> datetime | None:
    return raw if isinstance(raw, datetime) else None


def _num(policy: Mapping[str, Any], key: str, default: float) -> float:
    try:
        return float(policy.get(key, default))
    except (TypeError, ValueError):
        return default


@dataclass
class DayResult:
    regular_hours: Decimal = Decimal("0.00")
    ot_hours: Decimal = Decimal("0.00")
    dt_hours: Decimal = Decimal("0.00")
    premium_hours: Decimal = Decimal("0.00")
    meal_minutes: Decimal = Decimal("0.00")
    work_hours: Decimal = Decimal("0.00")
    rest_ok: bool = True
    meal_ok: bool = True
    premium_flags: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "regular_hours": float(self.regular_hours),
            "ot_hours": float(self.ot_hours),
            "dt_hours": float(self.dt_hours),
            "premium_hours": float(self.premium_hours),
            "meal_minutes": float(self.meal_minutes),
            "work_hours": float(self.work_hours),
            "rest_ok": self.rest_ok,
            "meal_ok": self.meal_ok,
            "premium_flags": list(self.premium_flags),
        }


def split_daily_hours(work_hours: Decimal, policy: Mapping[str, Any]) -> tuple[Decimal, Decimal, Decimal]:
    ot_after = Decimal(str(_num(policy, "ot_daily_hours", 8)))
    dt_after = Decimal(str(_num(policy, "dt_daily_hours", 12)))
    hours = max(Decimal("0.00"), work_hours)
    if hours <= ot_after:
        return hours, Decimal("0.00"), Decimal("0.00")
    if hours <= dt_after:
        return ot_after, hours - ot_after, Decimal("0.00")
    return ot_after, dt_after - ot_after, hours - dt_after


def _pay_units(regular: Decimal, ot: Decimal, dt: Decimal) -> Decimal:
    return regular + (ot * Decimal("1.5")) + (dt * Decimal("2"))


def entries_to_intervals(
    entries: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
) -> list[dict[str, Any]]:
    """Turn shift rows + nested punches into work/break intervals."""
    out: list[dict[str, Any]] = []
    for row in entries:
        start = _as_dt(row.get("start_at") or row.get("started_at"))
        if start is None:
            continue
        end = _as_dt(row.get("end_at") or row.get("ended_at")) or now
        punches = list(row.get("punches") or [])
        punches.sort(key=lambda p: _as_dt(p.get("occurred_at") or p.get("at")) or start)
        cursor = start
        open_break: datetime | None = None
        for punch in punches:
            at = _as_dt(punch.get("occurred_at") or punch.get("at"))
            if at is None:
                continue
            kind = str(punch.get("kind") or punch.get("event_type") or "")
            if kind == "break_start":
                if at > cursor:
                    out.append({"start_at": cursor, "end_at": at, "entry_type": "work"})
                open_break = at
                cursor = at
            elif kind == "break_end" and open_break is not None:
                out.append({"start_at": open_break, "end_at": at, "entry_type": "break_unpaid"})
                open_break = None
                cursor = at
        if open_break is not None:
            out.append({"start_at": open_break, "end_at": end, "entry_type": "break_unpaid"})
        elif end > cursor:
            out.append({"start_at": cursor, "end_at": end, "entry_type": "work"})
        if not punches:
            et = str(row.get("entry_type") or "work")
            out.append({"start_at": start, "end_at": end, "entry_type": et})
    return out


def compute_day(entries: Sequence[Mapping[str, Any]], policy: Mapping[str, Any], *, now: datetime | None = None) -> DayResult:
    """CA daily OT/DT plus meal detection. `entries` are intervals or shift+punch rows."""
    clock = now
    if clock is None:
        for row in entries:
            start = _as_dt(row.get("start_at") or row.get("started_at") or row.get("end_at"))
            if start is not None:
                clock = start
                break
        if clock is None:
            clock = datetime.now()
    intervals = []
    looks_like_shift = any(isinstance(e, Mapping) and "punches" in e for e in entries)
    if looks_like_shift:
        intervals = entries_to_intervals(entries, now=clock)
    else:
        for row in entries:
            start = _as_dt(row.get("start_at") or row.get("started_at"))
            end = _as_dt(row.get("end_at") or row.get("ended_at")) or clock
            if start is None:
                continue
            intervals.append(
                {
                    "start_at": start,
                    "end_at": end,
                    "entry_type": str(row.get("entry_type") or "work"),
                }
            )

    work_secs = 0.0
    meal_secs = 0.0
    paid_break_secs = 0.0
    first_in: datetime | None = None
    meal_ok = True
    rest_ok = True
    flags: list[str] = []
    unpaid_breaks: list[tuple[datetime, datetime]] = []

    for iv in intervals:
        start = iv["start_at"]
        end = iv["end_at"]
        if end < start:
            continue
        secs = (end - start).total_seconds()
        et = str(iv.get("entry_type") or "work")
        if et == "work":
            work_secs += secs
            if first_in is None or start < first_in:
                first_in = start
        elif et in ("break_unpaid", "break"):
            meal_secs += secs
            unpaid_breaks.append((start, end))
        elif et == "break_paid":
            paid_break_secs += secs

    work_hours = _hours(work_secs)
    meal_minutes = (Decimal(str(meal_secs)) / Decimal("60")).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    regular, ot, dt = split_daily_hours(work_hours, policy)

    meal_after = _num(policy, "meal_after_hours", 5)
    meal_min = _num(policy, "meal_minutes", 30)
    second_after = _num(policy, "second_meal_after_hours", 10)
    rest_per_4 = _num(policy, "rest_minutes_per_4h", 10)

    qualifying: list[tuple[datetime, datetime]] = []
    for b_start, b_end in unpaid_breaks:
        mins = (b_end - b_start).total_seconds() / 60.0
        if mins + 1e-6 >= meal_min:
            qualifying.append((b_start, b_end))

    if work_hours >= Decimal(str(meal_after)):
        meal_ok = False
        if first_in is not None:
            window_end = first_in + timedelta(hours=meal_after)
            for b_start, _b_end in qualifying:
                if b_start <= window_end:
                    meal_ok = True
                    break
        if not meal_ok:
            flags.append("missing_meal")

    if work_hours >= Decimal(str(second_after)):
        if len(qualifying) < 2:
            meal_ok = False
            if "missing_meal" not in flags:
                flags.append("missing_meal")

    rest_needed_min = rest_per_4 * int(float(work_hours) // 4)
    rest_got_min = paid_break_secs / 60.0
    if rest_needed_min > 0 and rest_got_min + 1e-6 < rest_needed_min:
        rest_ok = False
        flags.append("missing_rest")

    premium = Decimal("0.00")
    if "missing_meal" in flags:
        premium += Decimal("1.00")

    return DayResult(
        regular_hours=regular,
        ot_hours=ot,
        dt_hours=dt,
        premium_hours=premium,
        meal_minutes=meal_minutes,
        work_hours=work_hours,
        rest_ok=rest_ok,
        meal_ok=meal_ok,
        premium_flags=flags,
    )


def compute_week(days: Iterable[Mapping[str, Any]], policy: Mapping[str, Any]) -> dict[str, Any]:
    """Greater of daily-method vs weekly-method CA totals. 7th consecutive day is 1.5x/2x."""
    day_list = list(days)
    daily_reg = Decimal("0.00")
    daily_ot = Decimal("0.00")
    daily_dt = Decimal("0.00")
    daily_prem = Decimal("0.00")
    total_work = Decimal("0.00")
    worked_flags: list[bool] = []

    for day in day_list:
        reg = Decimal(str(day.get("regular_hours") or 0))
        ot = Decimal(str(day.get("ot_hours") or 0))
        dt = Decimal(str(day.get("dt_hours") or 0))
        prem = Decimal(str(day.get("premium_hours") or 0))
        work = Decimal(str(day.get("work_hours") or (reg + ot + dt)))
        daily_reg += reg
        daily_ot += ot
        daily_dt += dt
        daily_prem += prem
        total_work += work
        worked_flags.append(work > 0)

    weekly_ot_after = Decimal(str(_num(policy, "ot_weekly_hours", 40)))
    weekly_reg = min(total_work, weekly_ot_after)
    weekly_ot = max(Decimal("0.00"), total_work - weekly_ot_after)
    weekly_dt = Decimal("0.00")

    if policy.get("seventh_day_ot") and len(worked_flags) >= 7:
        consecutive = 0
        seventh_work = Decimal("0.00")
        for i, worked in enumerate(worked_flags):
            if worked:
                consecutive += 1
                if consecutive >= 7:
                    d = day_list[i]
                    seventh_work = Decimal(str(d.get("work_hours") or 0))
                    if seventh_work <= 0:
                        seventh_work = Decimal(str(d.get("regular_hours") or 0)) + Decimal(str(d.get("ot_hours") or 0)) + Decimal(
                            str(d.get("dt_hours") or 0)
                        )
            else:
                consecutive = 0
        if consecutive >= 7 and seventh_work > 0:
            # First 8 of the 7th day at 1.5x, after 8 at 2x — replace that day's weekly classification.
            day8 = Decimal("8.00")
            seventh_ot = min(seventh_work, day8)
            seventh_dt = max(Decimal("0.00"), seventh_work - day8)
            weekly_ot += seventh_ot
            weekly_dt += seventh_dt
            weekly_reg = max(Decimal("0.00"), weekly_reg - seventh_work)

    daily_units = _pay_units(daily_reg, daily_ot, daily_dt)
    weekly_units = _pay_units(weekly_reg, weekly_ot, weekly_dt)
    if weekly_units > daily_units:
        regular, ot, dt = weekly_reg, weekly_ot, weekly_dt
        method = "weekly"
    else:
        regular, ot, dt = daily_reg, daily_ot, daily_dt
        method = "daily"

    return {
        "regular_hours": float(regular.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
        "ot_hours": float(ot.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
        "dt_hours": float(dt.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
        "premium_hours": float(daily_prem.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
        "work_hours": float(total_work.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
        "method": method,
    }
