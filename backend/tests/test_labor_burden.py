"""Employer payroll-tax / unemployment / workers-comp burden on wage rates."""
from __future__ import annotations

from types import SimpleNamespace

from app.labor_burden import DEFAULT_LABOR_BURDEN, labor_burden_breakdown, normalize_labor_burden


def test_default_burden_adds_federal_payroll_taxes():
    row = SimpleNamespace(
        basic_hourly_rate="41.5",
        health_welfare="8.25",
        pension="6",
        vacation_holiday=None,
        other_payments=None,
        training=None,
        workers_comp_pct=None,
    )
    out = labor_burden_breakdown(row, DEFAULT_LABOR_BURDEN)
    assert out["fringe_hourly"] == 55.75
    assert out["taxable_hourly"] == 41.5
    assert out["burden_hourly"] == 3.4238
    assert out["total_loaded_hourly"] == 59.1738
    labels = {line["label"] for line in out["lines"]}
    assert "Social Security" in labels
    assert "Medicare" in labels
    assert "Federal unemployment (FUTA)" in labels
    assert "State unemployment" in labels
    assert "Workers' compensation" in labels


def test_vacation_is_taxable_and_trust_fringes_are_not():
    row = {
        "basic_hourly_rate": 40,
        "health_welfare": 10,
        "pension": 8,
        "vacation_holiday": 4,
        "training": 1,
    }
    out = labor_burden_breakdown(row, {"social_security_pct": 10, "medicare_pct": 0, "futa_pct": 0})
    assert out["taxable_hourly"] == 44.0
    assert out["fringe_hourly"] == 63.0
    assert out["burden_hourly"] == 4.4
    assert out["total_loaded_hourly"] == 67.4


def test_row_workers_comp_overrides_company_default():
    row = {"basic_hourly_rate": 50, "workers_comp_pct": 10}
    out = labor_burden_breakdown(row, {**DEFAULT_LABOR_BURDEN, "workers_comp_pct": 4})
    wc = next(line for line in out["lines"] if line["key"] == "workers_comp_pct")
    assert wc["pct"] == 10
    assert wc["amount"] == 5.0


def test_normalize_clamps_percentages():
    out = normalize_labor_burden({"social_security_pct": -1, "medicare_pct": 200, "futa_pct": 0.6})
    assert out["social_security_pct"] == 0.0
    assert out["medicare_pct"] == 100.0
    assert out["futa_pct"] == 0.6
    assert out["suta_pct"] == 0.0
