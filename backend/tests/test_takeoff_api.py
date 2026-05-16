"""API tests for lead estimate detail and takeoff line CRUD."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.lead_estimate import LeadEstimate
from app.models.project import Project
from app.models.takeoff_line_item import TakeoffLineItem


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


def test_project_takeoff_lines_list_includes_rollups(client):
    """GET /projects/<id>/takeoff-lines returns rollups alongside items (additive JSON)."""
    pid = None
    try:
        with client.application.app_context():
            p = Project(name="rollup API test project")
            db.session.add(p)
            db.session.flush()
            pid = p.id
            db.session.add(
                TakeoffLineItem(
                    project_id=pid,
                    lead_estimate_id=None,
                    description="Perimeter",
                    quantity=Decimal("10.5"),
                    unit="LF",
                    unit_cost=Decimal("2"),
                    extended_total=Decimal("21"),
                )
            )
            db.session.commit()
            pid_s = str(pid)

        r = client.get(f"/api/v1/projects/{pid_s}/takeoff-lines")
        assert r.status_code == 200, r.get_data(as_text=True)
        body = r.get_json()
        assert "items" in body and "entity" in body
        assert len(body["items"]) == 1
        assert "rollups" in body
        assert body["rollups"]["line_count"] == 1
        assert body["rollups"]["qty_sum_decimal"] == "10.5"
        assert body["rollups"]["by_unit"]["LF"] == "10.5"
    finally:
        if pid is not None:
            with client.application.app_context():
                for row in db.session.scalars(select(TakeoffLineItem).where(TakeoffLineItem.project_id == pid)).all():
                    db.session.delete(row)
                pro = db.session.get(Project, pid)
                if pro is not None:
                    db.session.delete(pro)
                db.session.commit()


def test_material_prices_list(client):
    r = client.get("/api/v1/material-prices?limit=5")
    assert r.status_code == 200
    j = r.get_json()
    assert j.get("entity") == "material_prices"
    assert "items" in j
    assert "total" in j
    assert "offset" in j


def test_material_prices_mounting_type_in_payload(client):
    from app.models.material_pricing import MaterialPrice

    try:
        with client.application.app_context():
            mp = MaterialPrice(
                manufacturer="TestMfg",
                item="Bracket-X",
                mounting_type="Surface",
                cost=Decimal("9.99"),
            )
            db.session.add(mp)
            db.session.commit()
            mid = mp.id
        r = client.get("/api/v1/material-prices?q=Bracket-X&limit=5")
        assert r.status_code == 200
        items = r.get_json().get("items") or []
        hit = next((x for x in items if x.get("id") == str(mid)), None)
        assert hit is not None
        assert hit.get("mounting_type") == "Surface"
    finally:
        with client.application.app_context():
            row = db.session.scalar(
                select(MaterialPrice).where(
                    MaterialPrice.manufacturer == "TestMfg",
                    MaterialPrice.item == "Bracket-X",
                )
            )
            if row is not None:
                db.session.delete(row)
                db.session.commit()


def test_takeoff_line_patch_location_and_material_catalog(client):
    from app.models.material_pricing import MaterialPrice

    eid = "test-tk-mat-" + uuid.uuid4().hex[:12]
    mid = None
    try:
        with client.application.app_context():
            le = LeadEstimate(external_id=eid, name="Mat link test", number="T-MAT-1")
            db.session.add(le)
            db.session.flush()
            mp = MaterialPrice(manufacturer="Acme", item="Widget A", cost=Decimal("12.34"))
            db.session.add(mp)
            db.session.flush()
            mid = mp.id
            db.session.commit()

        r = client.post(
            f"/api/v1/lead-estimates/{eid}/takeoff-lines",
            json={"description": "Line A", "quantity": 1, "unit": "EA", "unit_cost": 10, "cost_type": "M"},
        )
        assert r.status_code == 201
        line_id = r.get_json()["item"]["id"]

        r2 = client.patch(
            f"/api/v1/takeoff-lines/{line_id}",
            json={
                "takeoff_location": "North stair",
                "material_pricing_id": str(mid),
                "description": "Labeled row",
            },
        )
        assert r2.status_code == 200, r2.get_data(as_text=True)
        item = r2.get_json()["item"]
        assert item["takeoff_location"] == "North stair"
        assert item["material_pricing_id"] == str(mid)
        assert item["material_catalog"] is not None
        assert item["material_catalog"]["item"] == "Widget A"

        r3 = client.patch(f"/api/v1/takeoff-lines/{line_id}", json={"material_pricing_id": None})
        assert r3.status_code == 200
        assert r3.get_json()["item"]["material_pricing_id"] is None
        assert r3.get_json()["item"]["material_catalog"] is None

        client.delete(f"/api/v1/takeoff-lines/{line_id}")
    finally:
        with client.application.app_context():
            row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
            if row is not None:
                db.session.delete(row)
            if mid is not None:
                mp2 = db.session.get(MaterialPrice, mid)
                if mp2 is not None:
                    db.session.delete(mp2)
            db.session.commit()


