"""Golden State planroom weekly CSV parse + list/import API."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from sqlalchemy import delete

from app.extensions import db
from app.golden_state_planroom_csv import (
    parse_agcs_weekly_csv,
    parse_agcs_weekly_html,
    parse_agcs_weekly_listing,
    upsert_planroom_rows,
)
from app.golden_state_planroom_score import classify_building, score_planroom_lead
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

_SAMPLE_HTML = """<!DOCTYPE html><html><body>
<tr><td colspan="26"><nobr>WEEKLY&nbsp;PROJECT&nbsp;LISTING</nobr></td></tr>
<tr><td><nobr>August&nbsp;29,&nbsp;2026</nobr></td></tr>
<tr>
  <td><nobr>NEW</nobr></td>
  <td><nobr>9/10/2026</nobr></td>
  <td><nobr>2:00&nbsp;PM</nobr></td>
  <td><nobr>San&nbsp;Diego</nobr></td>
  <td><nobr>0</nobr></td>
  <td><nobr>99-00001</nobr></td>
  <td class="cs9E596F2C" onmousedown="ASPx.xr_NavigateUrl('https://login.onlineplanservice.com/filter.aspx?BidPackageID=1360001&amp;projectnum=AGCS99-00001&amp;bx=AGCS&amp;bxup=99-00001&#39;, &#39;&#39;)"><nobr>San&nbsp;Dieguito&nbsp;Lagoon</nobr><br/><nobr>Double&nbsp;Track</nobr></td>
  <td><nobr>$1,200,000.00</nobr></td>
</tr>
<tr>
  <td><nobr>*</nobr></td>
  <td><nobr>9/8/2026</nobr></td>
  <td><nobr>3:00&nbsp;PM</nobr></td>
  <td><nobr>San&nbsp;Diego</nobr></td>
  <td><nobr>3</nobr></td>
  <td><nobr>99-00002</nobr></td>
  <td class="cs9E596F2C" onmousedown="ASPx.xr_NavigateUrl('https://login.onlineplanservice.com/filter.aspx?BidPackageID=1360002&amp;projectnum=AGCS99-00002&amp;bx=AGCS&amp;bxup=99-00002&#39;, &#39;&#39;)"><nobr>Admiral&nbsp;Baker&nbsp;Golf&nbsp;Course</nobr></td>
  <td><nobr>$15,956,102.00</nobr></td>
</tr>
</body></html>
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


def test_parse_agcs_weekly_html():
    rows, week = parse_agcs_weekly_html(_SAMPLE_HTML)
    assert week == date(2026, 8, 29)
    assert len(rows) == 2
    first = next(r for r in rows if r["plan_number"] == "99-00001")
    assert first["is_new"] is True
    assert first["location"] == "San Diego"
    assert first["bid_date"] == date(2026, 9, 10)
    assert first["name"] == "San Dieguito Lagoon Double Track"
    assert first["project_url"] == (
        "https://login.onlineplanservice.com/filter.aspx"
        "?BidPackageID=1360001&projectnum=AGCS99-00001&bx=AGCS&bxup=99-00001"
    )
    baker = next(r for r in rows if r["plan_number"] == "99-00002")
    assert baker["bid_date_changed"] is True
    assert str(baker["estimate_high"]) == "15956102.00"


def test_html_import_keeps_project_url_after_csv(client, flask_app):
    _clear_sample(flask_app)
    uploaded = client.post(
        "/api/v1/golden-state-planroom/import",
        data={"file": (BytesIO(_SAMPLE_HTML.encode("utf-8")), "AGCS_CAProjects.html")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200, uploaded.get_data(as_text=True)
    listed = client.get("/api/v1/golden-state-planroom/leads?q=99-00001")
    assert listed.status_code == 200
    item = next(x for x in listed.get_json()["items"] if x["plan_number"] == "99-00001")
    assert item["project_url"] and "BidPackageID=1360001" in item["project_url"]

    csv_again = client.post(
        "/api/v1/golden-state-planroom/import",
        data={"file": (BytesIO(_SAMPLE.encode("utf-8")), "AGCS_CAProjects.csv")},
        content_type="multipart/form-data",
    )
    assert csv_again.status_code == 200, csv_again.get_data(as_text=True)
    listed = client.get("/api/v1/golden-state-planroom/leads?q=99-00001")
    item = next(x for x in listed.get_json()["items"] if x["plan_number"] == "99-00001")
    assert item["project_url"] and "BidPackageID=1360001" in item["project_url"]
    _clear_sample(flask_app)


def test_listing_dispatch_uses_html_when_filename_says_so():
    rows, _week = parse_agcs_weekly_listing(_SAMPLE_HTML, filename="AGCS_CAProjects.html")
    assert rows and rows[0]["project_url"]


def test_score_planroom_lead_matches_bid_profile():
    school = score_planroom_lead(
        name="Lincoln High School Modernization",
        location="San Diego",
        estimate_high="22000000",
    )
    assert school["building"] == "K-12"
    assert school["band"] == "strong"
    assert school["score"] >= 70

    rail = score_planroom_lead(
        name="San Dieguito Lagoon Double Track Project",
        location="San Diego",
        estimate_high=None,
    )
    assert rail["building_key"] == "infra"
    assert rail["band"] == "weak"
    assert rail["score"] < 45

    golf = score_planroom_lead(
        name="Admiral Baker Golf Course Renovation Project",
        location="San Diego",
        estimate_high="15956102",
    )
    assert golf["building_key"] == "recreation"
    assert golf["band"] == "possible"
    assert golf["score"] > rail["score"]
    assert golf["score"] < school["score"]


def test_classify_building_covers_core_types():
    assert classify_building("El Cajon Fire Station No. 9") == "civic"
    assert classify_building("Scripps Hospital Patient Tower") == "healthcare"
    assert classify_building("Grossmont Community College Science") == "higher_ed"
    assert classify_building("SMF Concourse B Expansion") == "aviation"
    assert classify_building("El Centro Wastewater Treatment Plant") == "infra"
    assert classify_building("Costco Depot") == "warehouse"
    assert classify_building("Moreno Valley Warehouse / Distribution Center") == "warehouse"

    depot = score_planroom_lead(
        name="Costco Depot",
        location="Riverside",
        estimate_high="45000000",
    )
    assert depot["building_key"] == "warehouse"
    assert depot["band"] == "strong"
    assert depot["score"] >= 70


def test_list_api_returns_fit_and_ranks_by_score(client, flask_app):
    _clear_sample(flask_app)
    extra = """AGC San Diego Chapter,,,,,,,,,,,,,,,,
WEEKLY PROJECT LISTING,,,,,,,,,,,,,,,,
"August 29, 2026",,,,,,,,,,,,,,,,
,,,,Bid Date,Bid Time,Location,# of Addenda,,,Plan #,,Project Name,,,,Estimate High
NEW, ,,9/10/2026,,2:00 PM   ,San Diego,,0,99-00001,,Lincoln High School Modernization,,,,"$22,000,000.00"
,*,,9/8/2026,,3:00 PM   ,San Diego,,3,99-00002,,Admiral Baker Golf Course Renovation Project,,,,"$15,956,102.00"
, ,,9/11/2026,,2:00 PM   ,Sacramento,,0,99-00003,,San Dieguito Lagoon Double Track Project,,,,
"""
    uploaded = client.post(
        "/api/v1/golden-state-planroom/import",
        data={"file": (BytesIO(extra.encode("utf-8")), "AGCS_CAProjects.csv")},
        content_type="multipart/form-data",
    )
    assert uploaded.status_code == 200, uploaded.get_data(as_text=True)

    ranked = client.get("/api/v1/golden-state-planroom/leads?q=99-000&sort=fit_score")
    assert ranked.status_code == 200
    items = [x for x in ranked.get_json()["items"] if x["plan_number"] in _SAMPLE_PLANS]
    assert items[0]["plan_number"] == "99-00001"
    assert items[0]["fit"]["band"] == "strong"
    assert items[-1]["plan_number"] == "99-00003"
    assert items[-1]["fit"]["band"] == "weak"

    strong = client.get("/api/v1/golden-state-planroom/leads?q=99-000&strong_only=1")
    assert strong.status_code == 200
    strong_items = [x for x in strong.get_json()["items"] if x["plan_number"] in _SAMPLE_PLANS]
    assert [x["plan_number"] for x in strong_items] == ["99-00001"]
    _clear_sample(flask_app)
