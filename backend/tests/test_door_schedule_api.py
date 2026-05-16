"""Door schedule import and takeoff line expansion."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.door_opening import DoorOpening
from app.models.lead_estimate import LeadEstimate
from app.models.takeoff_line_item import TakeoffLineItem


@pytest.fixture
def lead_external_id(client):
    eid = "test-door-" + uuid.uuid4().hex[:12]
    with client.application.app_context():
        le = LeadEstimate(external_id=eid, name="Door schedule test", number="D-1")
        db.session.add(le)
        db.session.commit()
    yield eid
    with client.application.app_context():
        row = db.session.scalar(select(LeadEstimate).where(LeadEstimate.external_id == eid))
        if row is not None:
            db.session.delete(row)
            db.session.commit()


def test_import_door_schedule_creates_openings_and_lines(client, lead_external_id):
    rows = [
        {
            "Door No.": "101",
            "Room": "Lobby",
            "Width": "3'-0\"",
            "Height": "7'-0\"",
            "Door Type": "Hollow metal",
            "Frame": "HM frame",
            "HW": "HD-1",
        },
        {
            "Door No.": "102",
            "Room": "Corridor",
            "Size": "3'-0\" x 7'-0\"",
            "Door Type": "Wood",
            "Frame": "KD frame",
            "HW": "HW-2",
        },
    ]
    column_map = {
        "mark": "Door No.",
        "room": "Room",
        "width": "Width",
        "height": "Height",
        "size": "Size",
        "door_type": "Door Type",
        "frame_type": "Frame",
        "hardware_set_code": "HW",
    }
    r = client.post(
        f"/api/v1/lead-estimates/{lead_external_id}/door-schedule/import",
        json={"rows": rows, "column_map": column_map, "mode": "replace"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["opening_count"] == 2
    assert body["created"] == 2

    r2 = client.get(f"/api/v1/lead-estimates/{lead_external_id}/door-schedule")
    assert r2.status_code == 200
    sched = r2.get_json()
    assert sched["opening_count"] == 2
    marks = {op["mark"] for op in sched["openings"]}
    assert marks == {"101", "102"}

    op101 = next(o for o in sched["openings"] if o["mark"] == "101")
    assert op101["takeoff_line_count"] >= 5
    roles = {ln["line_role"] for ln in op101["takeoff_lines"]}
    assert "door" in roles
    assert "frame" in roles
    assert "hardware" in roles

    r3 = client.get(f"/api/v1/lead-estimates/{lead_external_id}")
    assert r3.status_code == 200
    lead_lines = r3.get_json()["item"]["takeoff_lines"]
    assert len(lead_lines) >= 8
    assert all(ln.get("door_opening_id") for ln in lead_lines)


def test_patch_opening_rebuild_and_expand_hardware(client, lead_external_id):
    r = client.post(
        f"/api/v1/lead-estimates/{lead_external_id}/door-schedule/import",
        json={
            "rows": [{"Door": "201", "HW": ""}],
            "column_map": {"mark": "Door", "hardware_set_code": "HW"},
            "mode": "replace",
        },
    )
    assert r.status_code == 201
    op_id = r.get_json()["openings"][0]["id"]
    assert r.get_json()["openings"][0]["takeoff_line_count"] == 2

    r2 = client.patch(
        f"/api/v1/door-openings/{op_id}",
        json={"hardware_set_code": "HD-1", "rebuild_lines": True},
    )
    assert r2.status_code == 200
    item = r2.get_json()["item"]
    assert item["takeoff_line_count"] >= 5

    r3 = client.post(f"/api/v1/door-openings/{op_id}/expand-hardware")
    assert r3.status_code == 200
    assert r3.get_json()["hardware_lines_added"] >= 1


def test_create_hardware_set_and_item(client):
    code = "HD-" + str(uuid.uuid4().int % 90000 + 100)
    r = client.post(
        "/api/v1/door-hardware-sets",
        json={"code": code, "name": "Test set"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    r2 = client.post(
        f"/api/v1/door-hardware-sets/{code}/items",
        json={"label": "Surface closer", "default_qty": 1, "default_unit_cost": 99},
    )
    assert r2.status_code == 201
    item = r2.get_json()["item"]
    assert any(x["label"] == "Surface closer" for x in item["items"])


def test_create_single_door_opening(client, lead_external_id):
    r = client.post(
        f"/api/v1/lead-estimates/{lead_external_id}/door-openings",
        json={"mark": "301", "room": "Storage"},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["mark"] == "301"
    assert item["takeoff_line_count"] == 2
