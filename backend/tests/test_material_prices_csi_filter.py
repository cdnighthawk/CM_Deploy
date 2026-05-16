"""Material catalog CSI spec section filter (08 71 00 door hardware)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.material_pricing import MaterialPrice


@pytest.fixture
def material_rows(client):
    ids = []
    with client.application.app_context():
        a = MaterialPrice(
            manufacturer="TestMfg",
            item="hinge-" + uuid.uuid4().hex[:6],
            cost=10,
            csi_spec_section="087100",
        )
        b = MaterialPrice(
            manufacturer="TestMfg",
            item="dispenser-" + uuid.uuid4().hex[:6],
            cost=20,
            category="Baby Changing Station",
        )
        db.session.add(a)
        db.session.add(b)
        db.session.commit()
        ids = [str(a.id), str(b.id)]
    yield ids
    with client.application.app_context():
        for mid in ids:
            row = db.session.get(MaterialPrice, uuid.UUID(mid))
            if row is not None:
                db.session.delete(row)
        db.session.commit()


def test_material_prices_filter_csi_087100(client, material_rows):
    r = client.get("/api/v1/material-prices?csi_spec_section=087100&manufacturer=TestMfg&limit=500")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert all(x.get("csi_spec_section") == "087100" for x in items)
    assert any(x["item"].startswith("hinge-") for x in items)
    assert not any(x["item"].startswith("dispenser-") for x in items)


def test_cost_suggestions_material_csi_filter(client, material_rows):
    r = client.get("/api/v1/cost-suggestions/material?q=hinge&csi_spec_section=08%2071%2000")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) >= 1
    assert all(x.get("csi_spec_section") == "087100" for x in items)


def test_hardware_set_item_rejects_non_door_hardware_material(client, material_rows):
    with client.application.app_context():
        bad_id = db.session.scalar(
            select(MaterialPrice.id).where(MaterialPrice.csi_spec_section.is_(None))
        )
    assert bad_id is not None
    r = client.post(
        "/api/v1/door-hardware-sets/HD-99/items",
        json={
            "label": "Bad link",
            "material_pricing_id": str(bad_id),
        },
    )
    assert r.status_code == 400
    assert "087100" in (r.get_json().get("error") or "")
