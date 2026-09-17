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


def test_csi_storage_variants_include_spaced_display():
    from app.csi_spec import csi_storage_variants

    assert csi_storage_variants("10 11 00") == ["101100", "10 11 00"]
    assert csi_storage_variants("101100") == ["101100", "10 11 00"]
    assert csi_storage_variants("10 28 00") == ["102800", "10 28 00"]


def test_material_prices_query_includes_spaced_csi_variant():
    from app.api.v1 import _material_prices_query

    stmt = _material_prices_query("", "", csi_spec_section="10 11 00")
    compiled = str(stmt.compile(compile_kwargs={"literal_binds": True}))
    assert "101100" in compiled
    assert "10 11 00" in compiled


def test_material_prices_filter_matches_spaced_csi(client):
    ids = []
    sku = "board-" + uuid.uuid4().hex[:6]
    with client.application.app_context():
        row = MaterialPrice(
            manufacturer="SpacedCsiMfg",
            item=sku,
            cost=10,
            csi_spec_section="10 11 00",
        )
        db.session.add(row)
        db.session.commit()
        ids.append(str(row.id))
    try:
        for query in ("101100", "10%2011%2000"):
            r = client.get(
                f"/api/v1/material-prices?csi_spec_section={query}&manufacturer=SpacedCsiMfg&limit=50"
            )
            assert r.status_code == 200
            items = r.get_json()["items"]
            assert any(x["id"] == ids[0] for x in items), query
        facets = client.get("/api/v1/material-prices/facets?manufacturer=SpacedCsiMfg")
        assert facets.status_code == 200
        values = [x.get("value") for x in facets.get_json()["csi_sections"]]
        assert "101100" in values
        assert values.count("101100") == 1
        assert "10 11 00" not in values
    finally:
        with client.application.app_context():
            for mid in ids:
                row = db.session.get(MaterialPrice, uuid.UUID(mid))
                if row is not None:
                    db.session.delete(row)
            db.session.commit()


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
