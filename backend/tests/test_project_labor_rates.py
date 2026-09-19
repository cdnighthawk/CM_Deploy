"""Project labor rates: company wages plus housing, per diem, and mandated OT."""
from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.extensions import db
from app.labor_burden import DEFAULT_LABOR_BURDEN, labor_burden_breakdown
from app.models.lead_estimate import LeadEstimate
from app.models.wage_rate import WageRate
from app.project_labor_rates import is_hour_unit, ot_schedule, project_rate_breakdown, suggested_unit_cost


def test_default_schedule_matches_company_loaded():
    row = SimpleNamespace(
        basic_hourly_rate="41.5",
        health_welfare="8.25",
        pension="6",
        vacation_holiday=None,
        other_payments=None,
        training=None,
        workers_comp_pct=None,
        state="CA",
    )
    company = labor_burden_breakdown(row, DEFAULT_LABOR_BURDEN)
    out = project_rate_breakdown(
        row,
        {"hours_per_day": 8, "days_per_week": 5},
        DEFAULT_LABOR_BURDEN,
    )
    assert out["schedule"]["ot_hours"] == 0.0
    assert out["ot_hourly"] == 0.0
    assert out["per_diem_hourly"] == 0.0
    assert out["housing_hourly"] == 0.0
    assert out["project_loaded_hourly"] == company["total_loaded_hourly"]
    assert out["project_loaded_hourly"] == 59.1738


def test_five_by_ten_mandated_ot_adds_premium_and_burden():
    row = {
        "basic_hourly_rate": 41.5,
        "health_welfare": 8.25,
        "pension": 6,
        "state": "CA",
    }
    out = project_rate_breakdown(
        row,
        {"hours_per_day": 10, "days_per_week": 5},
        DEFAULT_LABOR_BURDEN,
    )
    assert out["schedule"]["clock_hours"] == 50.0
    assert out["schedule"]["st_hours"] == 40.0
    assert out["schedule"]["ot_hours"] == 10.0
    assert out["schedule"]["pay_factor"] == 1.1
    assert out["ot_premium_hourly"] == 4.15
    assert out["ot_burden_hourly"] == 0.3424
    assert out["ot_hourly"] == 4.4924
    assert out["company_loaded_hourly"] == 59.1738
    assert out["project_loaded_hourly"] == 63.6662


def test_per_diem_and_housing_convert_to_hourly():
    row = {"basic_hourly_rate": 41.5, "health_welfare": 8.25, "pension": 6}
    out = project_rate_breakdown(
        row,
        {
            "hours_per_day": 8,
            "days_per_week": 5,
            "per_diem_per_day": 80,
            "housing_per_week": 400,
        },
        DEFAULT_LABOR_BURDEN,
    )
    assert out["per_diem_hourly"] == 10.0
    assert out["housing_hourly"] == 10.0
    assert out["ot_hourly"] == 0.0
    assert out["project_loaded_hourly"] == 79.1738


def test_six_by_eight_weekly_ot():
    sched = ot_schedule(8, 6)
    assert sched["clock_hours"] == 48.0
    assert sched["st_hours"] == 40.0
    assert sched["ot_hours"] == 8.0
    assert sched["pay_factor"] == 1.083333


def _make_lead(external_id: str, **kwargs) -> LeadEstimate:
    le = LeadEstimate(external_id=external_id, name=kwargs.pop("name", "Labor rates parent"), **kwargs)
    db.session.add(le)
    db.session.commit()
    return le


def _cleanup_lead(external_id: str) -> None:
    row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == external_id))
    if row is not None:
        db.session.delete(row)
        db.session.commit()


def _delete_tagged_wage_rates(tag: str) -> None:
    rows = db.session.scalars(
        select(WageRate).where(WageRate.trade.ilike(f"%{tag}%"))
    ).all()
    for row in rows:
        db.session.delete(row)
    if rows:
        db.session.commit()


def test_labor_rates_get_put_and_lock(client, flask_app):
    eid = "labor-rate-" + uuid.uuid4().hex[:12]
    tag = uuid.uuid4().hex[:8]
    original_burden = (client.get("/api/v1/wage-rates/burden").get_json() or {}).get("burden")
    wage_id = None
    try:
        seed = client.put(
            "/api/v1/wage-rates/burden",
            json={
                "social_security_pct": 6.2,
                "medicare_pct": 1.45,
                "futa_pct": 0.6,
                "suta_pct": 0,
                "workers_comp_pct": 0,
                "other_pct": 0,
            },
        )
        assert seed.status_code == 200, seed.get_data(as_text=True)
        created_wage = client.post(
            "/api/v1/wage-rates",
            json={
                "state": "CA",
                "sub_area": "Test",
                "year": 2099,
                "trade": f"Painter {tag}",
                "basic_hourly_rate": "41.5",
                "health_welfare": "8.25",
                "pension": "6",
            },
        )
        assert created_wage.status_code == 201, created_wage.get_data(as_text=True)
        wage_id = created_wage.get_json()["item"]["id"]

        with flask_app.app_context():
            le = _make_lead(eid, location={"city": "Los Angeles", "state": "CA"})
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Bid"})
        assert created.status_code == 201, created.get_data(as_text=True)
        est_id = created.get_json()["item"]["id"]
        summary = created.get_json()["item"]["labor_rates"]
        assert summary["settings"]["state"] == "CA"
        assert summary["trades"] == []

        fetched = client.get(f"/api/v1/estimates/{est_id}/labor-rates")
        assert fetched.status_code == 200, fetched.get_data(as_text=True)
        item = fetched.get_json()["item"]
        assert item["settings"]["state"] == "CA"
        assert item["settings"]["hours_per_day"] == 8.0
        assert item["project_loaded_hourly"] is None

        saved = client.put(
            f"/api/v1/estimates/{est_id}/labor-rates",
            json={
                "state": "CA",
                "year": 2099,
                "hours_per_day": 10,
                "days_per_week": 5,
                "per_diem_per_day": 80,
                "housing_per_week": 400,
                "other_hourly": 1.5,
                "wage_rate_ids": [wage_id],
            },
        )
        assert saved.status_code == 200, saved.get_data(as_text=True)
        body = saved.get_json()["item"]
        assert body["settings"]["hours_per_day"] == 10.0
        assert body["schedule"]["ot_hours"] == 10.0
        assert len(body["trades"]) == 1
        trade = body["trades"][0]
        assert trade["wage_rate_id"] == wage_id
        assert trade["company_loaded_hourly"] == 59.1738
        assert trade["ot_hourly"] == 4.4924
        assert trade["per_diem_hourly"] == 8.0
        assert trade["housing_hourly"] == 8.0
        assert trade["other_hourly"] == 1.5
        assert trade["project_loaded_hourly"] == 81.1662

        again = client.get(f"/api/v1/estimates/{est_id}/labor-rates")
        assert again.status_code == 200
        assert again.get_json()["item"]["trades"][0]["project_loaded_hourly"] == 81.1662

        copied = client.post(
            f"/api/v1/leads/{lid}/estimates",
            json={"name": "Rev A", "copy_from_estimate_id": est_id},
        )
        assert copied.status_code == 201, copied.get_data(as_text=True)
        copy_rates = copied.get_json()["item"]["labor_rates"]
        assert copy_rates["settings"]["hours_per_day"] == 10.0
        assert copy_rates["trades"][0]["project_loaded_hourly"] == 81.1662

        locked = client.post(f"/api/v1/estimates/{est_id}/lock")
        assert locked.status_code == 200, locked.get_data(as_text=True)
        denied = client.put(
            f"/api/v1/estimates/{est_id}/labor-rates",
            json={"hours_per_day": 8, "wage_rate_ids": [wage_id]},
        )
        assert denied.status_code == 403
        assert denied.get_json()["error_code"] == "ESTIMATE_LOCKED"
    except ProgrammingError as exc:
        pytest.skip(f"labor_rates column missing (run flask db upgrade): {exc}")
    finally:
        if original_burden:
            client.put("/api/v1/wage-rates/burden", json=original_burden)
        with flask_app.app_context():
            if wage_id:
                _delete_tagged_wage_rates(tag)
            _cleanup_lead(eid)


def test_hour_unit_and_mixed_crew_unit_cost():
    assert is_hour_unit("HR")
    assert is_hour_unit("man-hours")
    assert not is_hour_unit("CY")
    op = str(uuid.uuid4())
    lab = str(uuid.uuid4())
    rates = {
        op: {"project_loaded_hourly": 100},
        lab: {"project_loaded_hourly": 50},
    }
    single = suggested_unit_cost(
        wage_rate_id=op,
        labor_crew=None,
        quantity=8,
        unit="HR",
        rates_by_id=rates,
    )
    assert single == 100
    mixed = suggested_unit_cost(
        wage_rate_id=op,
        labor_crew=[
            {"wage_rate_id": op, "hours": 8},
            {"wage_rate_id": lab, "hours": 16},
        ],
        quantity=10,
        unit="CY",
        rates_by_id=rates,
    )
    assert mixed == 160


def test_import_company_trades_and_assign_labor_line(client, flask_app):
    eid = "labor-line-" + uuid.uuid4().hex[:12]
    tag = uuid.uuid4().hex[:8]
    original_burden = (client.get("/api/v1/wage-rates/burden").get_json() or {}).get("burden")
    try:
        seed = client.put(
            "/api/v1/wage-rates/burden",
            json={
                "social_security_pct": 6.2,
                "medicare_pct": 1.45,
                "futa_pct": 0.6,
                "suta_pct": 0,
                "workers_comp_pct": 0,
                "other_pct": 0,
            },
        )
        assert seed.status_code == 200, seed.get_data(as_text=True)
        operator = client.post(
            "/api/v1/wage-rates",
            json={
                "state": "CA",
                "sub_area": "Test",
                "year": 2098,
                "trade": f"Operator {tag}",
                "basic_hourly_rate": "41.5",
                "health_welfare": "8.25",
                "pension": "6",
            },
        )
        assert operator.status_code == 201, operator.get_data(as_text=True)
        laborer = client.post(
            "/api/v1/wage-rates",
            json={
                "state": "CA",
                "sub_area": "Test",
                "year": 2098,
                "trade": f"Laborer {tag}",
                "basic_hourly_rate": "20.75",
                "health_welfare": "8.25",
                "pension": "6",
            },
        )
        assert laborer.status_code == 201, laborer.get_data(as_text=True)
        carpenter = client.post(
            "/api/v1/wage-rates",
            json={
                "state": "CA",
                "sub_area": "Test",
                "year": 2098,
                "trade": f"Carpenter {tag}",
                "basic_hourly_rate": "41.5",
                "health_welfare": "8.25",
                "pension": "6",
            },
        )
        assert carpenter.status_code == 201, carpenter.get_data(as_text=True)
        op_id = operator.get_json()["item"]["id"]
        lab_id = laborer.get_json()["item"]["id"]
        carp_id = carpenter.get_json()["item"]["id"]

        with flask_app.app_context():
            le = _make_lead(eid, location={"city": "Los Angeles", "state": "CA"})
            lid = str(le.id)

        created = client.post(f"/api/v1/leads/{lid}/estimates", json={"name": "Foundations"})
        assert created.status_code == 201, created.get_data(as_text=True)
        est_id = created.get_json()["item"]["id"]

        imported = client.post(
            f"/api/v1/estimates/{est_id}/labor-rates/import-company",
            json={"state": "CA", "year": 2098, "sub_area": "Test"},
        )
        assert imported.status_code == 200, imported.get_data(as_text=True)
        body = imported.get_json()["item"]
        ids = {row["wage_rate_id"] for row in body["trades"]}
        assert {op_id, lab_id, carp_id} <= ids
        assert body["imported_count"] >= 3
        assert any(row.get("from_company") for row in body["trades"])
        by_id = {row["wage_rate_id"]: row for row in body["trades"]}

        hourly = client.post(
            f"/api/v1/estimates/{est_id}/takeoff-lines",
            json={
                "description": "Operator time",
                "quantity": 8,
                "unit": "HR",
                "cost_type": "L",
                "wage_rate_id": op_id,
                "apply_labor_rate": True,
            },
        )
        assert hourly.status_code == 201, hourly.get_data(as_text=True)
        hour_line = hourly.get_json()["item"]
        assert hour_line["wage_rate_id"] == op_id
        assert hour_line["labor_trade"] == f"Operator {tag}"
        assert hour_line["unit_cost"] == by_id[op_id]["project_loaded_hourly"]
        assert hour_line["extended_total"] == pytest.approx(8 * by_id[op_id]["project_loaded_hourly"], abs=0.02)

        crew = client.post(
            f"/api/v1/estimates/{est_id}/takeoff-lines",
            json={
                "description": "Concrete foundations",
                "quantity": 10,
                "unit": "CY",
                "cost_type": "L",
                "labor_crew": [
                    {"wage_rate_id": op_id, "hours": 8},
                    {"wage_rate_id": lab_id, "hours": 16},
                    {"wage_rate_id": carp_id, "hours": 8},
                ],
                "apply_labor_rate": True,
            },
        )
        assert crew.status_code == 201, crew.get_data(as_text=True)
        crew_line = crew.get_json()["item"]
        total = (
            8 * by_id[op_id]["project_loaded_hourly"]
            + 16 * by_id[lab_id]["project_loaded_hourly"]
            + 8 * by_id[carp_id]["project_loaded_hourly"]
        )
        assert crew_line["labor_trade"].startswith("Crew (3")
        assert len(crew_line["labor_crew"]) == 3
        assert crew_line["unit_cost"] == pytest.approx(total / 10, abs=0.0002)
        assert crew_line["extended_total"] == pytest.approx(total, abs=0.02)
    except ProgrammingError as exc:
        pytest.skip(f"labor trade columns missing (run flask db upgrade): {exc}")
    finally:
        if original_burden:
            client.put("/api/v1/wage-rates/burden", json=original_burden)
        with flask_app.app_context():
            _delete_tagged_wage_rates(tag)
            _cleanup_lead(eid)
