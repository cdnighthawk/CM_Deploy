"""Material catalog CSI columns and bulk field updates."""
from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models.material_pricing import MaterialPrice


@pytest.fixture
def catalog_rows(client):
    ids = []
    with client.application.app_context():
        a = MaterialPrice(
            manufacturer="BulkMfg",
            item="hinge-" + uuid.uuid4().hex[:6],
            category="Hardware",
            cost=Decimal("10"),
            csi_spec_section="087100",
        )
        b = MaterialPrice(
            manufacturer="BulkMfg",
            item="dispenser-" + uuid.uuid4().hex[:6],
            category="Accessories",
            cost=Decimal("20"),
        )
        db.session.add_all([a, b])
        db.session.commit()
        ids = [str(a.id), str(b.id)]
    yield ids
    with client.application.app_context():
        for mid in ids:
            row = db.session.get(MaterialPrice, uuid.UUID(mid))
            if row is not None:
                db.session.delete(row)
        db.session.commit()


def test_material_prices_include_csi_display(client, catalog_rows):
    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&csi_spec_section=087100&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    hit = next(x for x in items if x["id"] == catalog_rows[0])
    assert hit["csi_spec_section"] == "087100"
    assert hit["csi_display"] == "08 71 00"
    assert hit["csi_division"] == "08"
    assert hit["csi_division_name"] == "Openings"


def test_material_prices_filter_csi_division(client, catalog_rows):
    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&csi_division=08&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(x["id"] == catalog_rows[0] for x in items)
    assert not any(x["id"] == catalog_rows[1] for x in items)


def test_material_price_csi_sections_and_ids(client, catalog_rows):
    sections = client.get("/api/v1/material-prices/csi-sections")
    assert sections.status_code == 200
    body = sections.get_json()
    assert any(x.get("csi_spec_section") == "087100" for x in body["items"])
    assert any(x.get("csi_division") == "08" for x in body["divisions"])

    ids = client.get("/api/v1/material-prices/ids?manufacturer=BulkMfg")
    assert ids.status_code == 200
    listed = set(ids.get_json()["ids"])
    assert set(catalog_rows).issubset(listed)


def test_bulk_change_csi_on_selected_rows(client, catalog_rows):
    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": catalog_rows, "field": "csi_spec_section", "value": "10 44 00"},
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["updated_count"] == 2
    assert all(x["csi_spec_section"] == "104400" for x in body["updated"])
    assert all(x["csi_display"] == "10 44 00" for x in body["updated"])
    assert all(x["csi_division"] == "10" for x in body["updated"])

    listed = client.get("/api/v1/material-prices?manufacturer=BulkMfg&limit=50")
    by_id = {x["id"]: x for x in listed.get_json()["items"]}
    assert by_id[catalog_rows[0]]["csi_spec_section"] == "104400"
    assert by_id[catalog_rows[1]]["csi_spec_section"] == "104400"


def test_material_prices_column_filters(client, catalog_rows):
    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&category=Hardware&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(x["id"] == catalog_rows[0] for x in items)
    assert not any(x["id"] == catalog_rows[1] for x in items)

    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&item=dispenser-&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(x["id"] == catalog_rows[1] for x in items)
    assert not any(x["id"] == catalog_rows[0] for x in items)

    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&csi_division=Openings&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(x["id"] == catalog_rows[0] for x in items)
    assert not any(x["id"] == catalog_rows[1] for x in items)


def test_material_price_categories_and_size(client, catalog_rows):
    cats = client.get("/api/v1/material-prices/categories")
    assert cats.status_code == 200
    names = cats.get_json()["items"]
    assert "Hardware" in names
    assert "Accessories" in names

    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&category=hard&limit=50")
    assert r.status_code == 200
    assert r.get_json()["items"] == []

    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": [catalog_rows[0]], "field": "size_width_in", "value": "48"},
    )
    assert r.status_code == 200, r.get_json()
    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": [catalog_rows[0]], "field": "size_height_in", "value": "96"},
    )
    assert r.status_code == 200, r.get_json()
    listed = client.get("/api/v1/material-prices?manufacturer=BulkMfg&size=48x96&limit=50")
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    hit = next(x for x in items if x["id"] == catalog_rows[0])
    assert hit["size_display"] == "48×96"
    assert hit["sheet_area_sf"] == 32.0
    assert not any(x["id"] == catalog_rows[1] for x in items)


def test_bulk_change_rejects_unknown_field(client, catalog_rows):
    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": catalog_rows, "field": "id", "value": "nope"},
    )
    assert r.status_code == 400
