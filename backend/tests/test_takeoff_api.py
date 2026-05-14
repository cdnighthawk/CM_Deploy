"""API tests for lead estimate detail and takeoff line CRUD."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.lead_estimate import LeadEstimate


def test_get_lead_estimate_unknown(client):
    r = client.get("/api/v1/lead-estimates/00000000-0000-0000-0000-000000000001")
    assert r.status_code == 404


def test_takeoff_line_crud(client):
    eid = "test-takeoff-" + uuid.uuid4().hex[:12]
    with client.application.app_context():
        le = LeadEstimate(external_id=eid, name="API test lead", number="T-API-1")
        db.session.add(le)
        db.session.commit()

    try:
        r = client.post(
            f"/api/v1/lead-estimates/{eid}/takeoff-lines",
            json={"description": "Line A", "quantity": 2, "unit": "EA", "unit_cost": 10, "cost_type": "M"},
        )
        assert r.status_code == 201, r.get_data(as_text=True)
        body = r.get_json()
        assert body["item"]["extended_total"] == 20.0
        line_id = body["item"]["id"]

        r2 = client.get(f"/api/v1/lead-estimates/{eid}")
        assert r2.status_code == 200
        item = r2.get_json()["item"]
        assert item["external_id"] == eid
        assert len(item["takeoff_lines"]) == 1

        r3 = client.patch(f"/api/v1/takeoff-lines/{line_id}", json={"quantity": 3})
        assert r3.status_code == 200
        assert r3.get_json()["item"]["extended_total"] == 30.0

        r4 = client.delete(f"/api/v1/takeoff-lines/{line_id}")
        assert r4.status_code == 200

        r5 = client.get(f"/api/v1/lead-estimates/{eid}")
        assert len(r5.get_json()["item"]["takeoff_lines"]) == 0

        r6 = client.post(
            f"/api/v1/lead-estimates/{eid}/takeoff-lines",
            json={"description": "Measured", "quantity": 1, "unit": "LF", "unit_cost": 5, "cost_type": "M"},
        )
        assert r6.status_code == 201, r6.get_data(as_text=True)
        line2 = r6.get_json()["item"]["id"]
        did = str(uuid.uuid4())
        r7 = client.patch(
            f"/api/v1/takeoff-lines/{line2}",
            json={
                "drawing_id": did,
                "measurement_data": {"tool": "linear_stub", "points": [[0, 0], [10, 0]], "page": 1},
                "quantity": 12.5,
            },
        )
        assert r7.status_code == 200, r7.get_data(as_text=True)
        body7 = r7.get_json()["item"]
        assert body7["drawing_id"] == did
        assert body7["measurement_data"]["tool"] == "linear_stub"
        assert body7["quantity"] == 12.5
        assert body7["extended_total"] == 62.5

        r8 = client.get(f"/api/v1/lead-estimates/{eid}/takeoff-lines")
        assert r8.status_code == 200
        items = r8.get_json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == line2
        assert items[0]["measurement_data"]["page"] == 1

        r9 = client.patch(f"/api/v1/takeoff-lines/{line2}", json={"measurement_data": None, "drawing_id": ""})
        assert r9.status_code == 200
        body9 = r9.get_json()["item"]
        assert body9["measurement_data"] is None
        assert body9["drawing_id"] is None

        client.delete(f"/api/v1/takeoff-lines/{line2}")
    finally:
        with client.application.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            if row is not None:
                db.session.delete(row)
                db.session.commit()


def test_cost_suggestions_material_short_query(client):
    r = client.get("/api/v1/cost-suggestions/material?q=a")
    assert r.status_code == 200
    assert r.get_json()["items"] == []
