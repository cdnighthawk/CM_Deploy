"""Employer payroll-tax / unemployment / workers-comp burden on wage rates."""
from __future__ import annotations

from types import SimpleNamespace

from app.labor_burden import (
    DEFAULT_LABOR_BURDEN,
    labor_burden_breakdown,
    labor_burden_for_state,
    normalize_labor_burden,
    normalize_labor_burden_book,
    normalize_state_code,
    public_labor_burden,
)


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


def test_state_codes_accept_names_and_abbreviations():
    assert normalize_state_code("ca") == "CA"
    assert normalize_state_code("California") == "CA"
    assert normalize_state_code("Hawaii") == "HI"
    assert normalize_state_code("FL") == "FL"


def test_book_always_includes_home_states():
    book = normalize_labor_burden_book({"suta_pct": 3.4, "workers_comp_pct": 12})
    assert set(book["states"]) >= {"CA", "FL", "HI"}
    assert book["states"]["CA"]["suta_pct"] == 3.4
    assert book["states"]["HI"]["workers_comp_pct"] == 12
    public = public_labor_burden(book)
    assert [row["state"] for row in public["states"][:3]] == ["CA", "FL", "HI"]
    assert public["catalog"][0]["state"] == "AL"


def test_burden_uses_the_row_state():
    book = {
        "states": [
            {"state": "CA", "suta_pct": 3.4, "workers_comp_pct": 10, "other_pct": 0},
            {"state": "FL", "suta_pct": 0.1, "workers_comp_pct": 4, "other_pct": 0},
            {"state": "HI", "suta_pct": 4, "workers_comp_pct": 8, "other_pct": 1},
        ]
    }
    ca = labor_burden_for_state(book, "California")
    fl = labor_burden_for_state(book, "FL")
    assert ca["suta_pct"] == 3.4
    assert ca["workers_comp_pct"] == 10
    assert fl["suta_pct"] == 0.1
    assert fl["workers_comp_pct"] == 4
    row = {"state": "HI", "basic_hourly_rate": 50}
    out = labor_burden_breakdown(row, book)
    assert out["burden_pct"] == 21.25
    assert out["burden_hourly"] == 10.625
