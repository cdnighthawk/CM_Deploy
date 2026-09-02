"""CA overtime / meal engine — no Flask."""
from datetime import datetime, timedelta, timezone

from app.api._time_ot import compute_day, compute_week, split_daily_hours
from app.api._time_policy import DEFAULT_TIME_POLICY
from decimal import Decimal


def test_split_daily_8_12():
    reg, ot, dt = split_daily_hours(Decimal("8.00"), DEFAULT_TIME_POLICY)
    assert reg == Decimal("8.00") and ot == 0 and dt == 0
    reg, ot, dt = split_daily_hours(Decimal("10.00"), DEFAULT_TIME_POLICY)
    assert reg == Decimal("8.00") and ot == Decimal("2.00") and dt == 0
    reg, ot, dt = split_daily_hours(Decimal("13.00"), DEFAULT_TIME_POLICY)
    assert reg == Decimal("8.00") and ot == Decimal("4.00") and dt == Decimal("1.00")


def test_missing_meal_on_8h_without_break():
    start = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=8)
    result = compute_day(
        [{"start_at": start, "end_at": end, "entry_type": "work"}],
        DEFAULT_TIME_POLICY,
        now=end,
    )
    assert result.work_hours == Decimal("8.00")
    assert result.meal_ok is False
    assert "missing_meal" in result.premium_flags


def test_meal_ok_with_30min_before_fifth_hour():
    start = datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
    meal = start + timedelta(hours=4)
    result = compute_day(
        [
            {"start_at": start, "end_at": meal, "entry_type": "work"},
            {"start_at": meal, "end_at": meal + timedelta(minutes=30), "entry_type": "break_unpaid"},
            {"start_at": meal + timedelta(minutes=30), "end_at": start + timedelta(hours=8, minutes=30), "entry_type": "work"},
        ],
        DEFAULT_TIME_POLICY,
        now=start + timedelta(hours=9),
    )
    assert result.meal_ok is True
    assert "missing_meal" not in result.premium_flags
    assert result.regular_hours == Decimal("8.00")


def test_week_greater_of_daily_vs_weekly():
    days = []
    for i in range(5):
        days.append({"regular_hours": 8, "ot_hours": 2, "dt_hours": 0, "work_hours": 10, "premium_hours": 0})
    week = compute_week(days, DEFAULT_TIME_POLICY)
    # daily method: 40 reg + 10 OT; weekly: 40 reg + 10 OT — same hours, daily units may equal weekly
    assert week["work_hours"] == 50
    assert week["regular_hours"] == 40
    assert week["ot_hours"] == 10


def test_seventh_day_ot():
    days = [{"regular_hours": 8, "ot_hours": 0, "dt_hours": 0, "work_hours": 8, "premium_hours": 0} for _ in range(7)]
    week = compute_week(days, DEFAULT_TIME_POLICY)
    assert week["work_hours"] == 56
    # 7th day first 8 at OT
    assert week["ot_hours"] >= 8
