"""Golden State planroom weekly CSV parse + list/import API."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from sqlalchemy import delete

from app.extensions import db
from app.golden_state_planroom_csv import parse_agcs_weekly_csv, upsert_planroom_rows
from app.models.golden_state_planroom_lead import GoldenStatePlanroomLead

_SAMPLE_PLANS = ("99-00001", "99-00002", "99-00003")


def _clear_sample(flask_app):
    with flask_app.app_context():
        db.session.execute(
            delete(GoldenStatePlanroomLead).where(GoldenStatePlanroomLead.plan_number.in_(_SAMPLE_PLANS))
        )
        db.session.commit()

_SAMPLE = """AGC San Diego Chapter,,,,,,,,,,,,,,,,
WEEKLY PROJECT LISTING,,,,,,,,,,,,,,,,
"August 29, 2026",,,,,,,,,,,,,,,,
,,,,Bid Date,Bid Time,Location,# of Addenda,,,Plan #,,Project Name,,,,Estimate High
NEW, ,,9/10/2026,,2:00 PM   ,San Diego,,0,99-00001,,San Dieguito Lagoon Double Track Project,,,,
,*,,9/8/2026,,3:00 PM   ,San Diego,,3,99-00002,,Admiral Baker Golf Course Renovation Project,,,,"$15,956,102.00"
, ,,9/11/2026,,2:00 PM   ,Sacramento,,0,99-00003,,Smf Concourse B Expansion,,,,
NEW, ,,9/10/2026,,2:00 PM   ,San Diego,,1,99-00001,,San Dieguito Lagoon Double Track Project (reprint),,,,
"""


def test_parse_agcs_weekly_csv():
    rows, week = parse_agcs_weekly_csv(_SAMPLE)
    assert week == date(2026, 8, 29)
    assert len(rows) == 4
    sd = next(r for r in rows if r["plan_number"] == "99-00001")
    assert sd["is_new"] is True
    assert sd["location"] == "San Diego"
    assert sd["bid_date"] == date(2026, 9, 10)
    baker = next(r for r in rows if r["plan_number"] == "99-00002")
    assert baker["bid_date_changed"] is True
    assert baker["estimate_high"] is not None
    assert str(baker["estimate_high"]) == "15956102.00"


def test_list_and_import_api(client, flask_app):
    _clear_sample(flask_app)

    uploaded = client.post(
        "/api/v1/golden-state-planroom/import",
        data={"file": (BytesIO(_SAMPLE.encode("utf-8")), "AGCS_CAProjects.csv")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200, uploaded.get_data(as_text=True)
    body = uploaded.get_json()
    assert body["loaded"] == 3
    assert body["listing_week"] == "2026-08-29"

    all_rows = client.get("/api/v1/golden-state-planroom/leads?q=99-00001")
    assert all_rows.status_code == 200
    items = all_rows.get_json()["items"]
    assert any(x["plan_number"] == "99-00001" for x in items)
    names = {x["plan_number"]: x["name"] for x in items}
    assert "reprint" in names["99-00001"].lower()

    sd = client.get("/api/v1/golden-state-planroom/leads?q=99-00001&new_only=1")
    assert sd.status_code == 200
    items = sd.get_json()["items"]
    assert items[0]["plan_number"] == "99-00001"

    _clear_sample(flask_app)


def test_upsert_dedupes_plan_number(flask_app):
    rows, _week = parse_agcs_weekly_csv(_SAMPLE)
    _clear_sample(flask_app)
    with flask_app.app_context():
        first, _ = upsert_planroom_rows(db.session, rows, source_file="a.csv")
        second, _ = upsert_planroom_rows(db.session, rows, source_file="b.csv")
        count = db.session.query(GoldenStatePlanroomLead).filter(
            GoldenStatePlanroomLead.plan_number.in_(_SAMPLE_PLANS)
        ).count()
    _clear_sample(flask_app)
    assert first == 3
    assert second == 3
    assert count == 3
