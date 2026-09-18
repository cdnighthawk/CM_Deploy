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


def test_material_price_facets_and_exact_dropdowns(client, catalog_rows):
    with client.application.app_context():
        row = db.session.get(MaterialPrice, uuid.UUID(catalog_rows[0]))
        row.mounting_type = "Surface"
        row.unit_of_measure = "EA"
        row.labor_per = Decimal("1")
        row.size_width_in = Decimal("24")
        row.size_height_in = Decimal("36")
        db.session.commit()

    facets = client.get("/api/v1/material-prices/facets")
    assert facets.status_code == 200
    body = facets.get_json()
    assert "BulkMfg" in body["manufacturers"]
    assert "Hardware" in body["categories"]
    assert "Accessories" in body["categories"]
    assert "Surface" in body["mounting_types"]
    assert "EA" in body["units"]
    assert "1" in body["labor"]
    assert "24×36" in body["sizes"]
    assert any(x.get("value") == "087100" for x in body["csi_sections"])

    r = client.get("/api/v1/material-prices?manufacturer=Bulk&limit=50")
    assert r.status_code == 200
    ids = {x["id"] for x in r.get_json()["items"]}
    assert catalog_rows[0] not in ids
    assert catalog_rows[1] not in ids

    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&mounting_type=Surface&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(x["id"] == catalog_rows[0] for x in items)
    assert not any(x["id"] == catalog_rows[1] for x in items)

    r = client.get("/api/v1/material-prices?manufacturer=BulkMfg&labor_per=1&limit=50")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(x["id"] == catalog_rows[0] for x in items)
    assert not any(x["id"] == catalog_rows[1] for x in items)


def test_material_price_facets_follow_other_filters(client, catalog_rows):
    extra_id = None
    with client.application.app_context():
        extra = MaterialPrice(
            manufacturer="OtherMfg-" + uuid.uuid4().hex[:6],
            item="locker-" + uuid.uuid4().hex[:6],
            category="Lockers",
            csi_spec_section="105113",
        )
        db.session.add(extra)
        db.session.commit()
        extra_id = str(extra.id)
        extra_mfr = extra.manufacturer
    try:
        by_mfr = client.get("/api/v1/material-prices/facets?manufacturer=BulkMfg")
        assert by_mfr.status_code == 200
        body = by_mfr.get_json()
        assert "Hardware" in body["categories"]
        assert "Accessories" in body["categories"]
        assert "Lockers" not in body["categories"]
        assert "BulkMfg" in body["manufacturers"]
        assert extra_mfr in body["manufacturers"]
        assert any(x.get("value") == "087100" for x in body["csi_sections"])
        assert not any(x.get("value") == "105113" for x in body["csi_sections"])

        by_csi = client.get("/api/v1/material-prices/facets?csi_spec_section=105113")
        assert by_csi.status_code == 200
        csi_body = by_csi.get_json()
        assert extra_mfr in csi_body["manufacturers"]
        assert "BulkMfg" not in csi_body["manufacturers"]
        assert "Lockers" in csi_body["categories"]
        assert "Hardware" not in csi_body["categories"]
    finally:
        with client.application.app_context():
            row = db.session.get(MaterialPrice, uuid.UUID(extra_id))
            if row is not None:
                db.session.delete(row)
                db.session.commit()


def test_bulk_change_rejects_unknown_field(client, catalog_rows):
    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": catalog_rows, "field": "id", "value": "nope"},
    )
    assert r.status_code == 400


def test_bulk_delete_selected_rows(client, catalog_rows):
    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": catalog_rows, "action": "delete"},
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["deleted_count"] == 2
    assert set(body["deleted"]) == set(catalog_rows)

    listed = client.get("/api/v1/material-prices?manufacturer=BulkMfg&limit=50")
    leftover = {x["id"] for x in listed.get_json()["items"]}
    assert not set(catalog_rows) & leftover


def test_bulk_delete_via_field_and_skips_missing(client, catalog_rows):
    missing = str(uuid.uuid4())
    r = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": [catalog_rows[0], missing], "field": "delete"},
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["deleted_count"] == 1
    assert body["deleted"] == [catalog_rows[0]]
    assert body["failed_count"] == 1

    gone = client.get(f"/api/v1/material-prices/{catalog_rows[0]}")
    assert gone.status_code == 404
    kept = client.get(f"/api/v1/material-prices/{catalog_rows[1]}")
    assert kept.status_code == 200


def test_get_material_price_detail(client, catalog_rows):
    r = client.get(f"/api/v1/material-prices/{catalog_rows[0]}")
    assert r.status_code == 200
    item = r.get_json()["item"]
    assert item["id"] == catalog_rows[0]
    assert item["manufacturer"] == "BulkMfg"
    assert item["csi_display"] == "08 71 00"
    assert "created_at" in item
    assert "updated_at" in item


def test_get_material_price_not_found(client):
    missing = uuid.uuid4()
    r = client.get(f"/api/v1/material-prices/{missing}")
    assert r.status_code == 404


def test_patch_material_price(client, catalog_rows):
    r = client.patch(
        f"/api/v1/material-prices/{catalog_rows[0]}",
        json={
            "description": "Updated hinge",
            "cost": "12.50",
            "csi_spec_section": "10 44 00",
            "mounting_type": "Recessed",
        },
    )
    assert r.status_code == 200, r.get_json()
    item = r.get_json()["item"]
    assert item["description"] == "Updated hinge"
    assert item["cost"] == 12.5
    assert item["csi_spec_section"] == "104400"
    assert item["csi_display"] == "10 44 00"
    assert item["mounting_type"] == "Recessed"

    listed = client.get("/api/v1/material-prices?manufacturer=BulkMfg&limit=50")
    hit = next(x for x in listed.get_json()["items"] if x["id"] == catalog_rows[0])
    assert hit["description"] == "Updated hinge"


def test_patch_production_rate_derives_hours_and_uom(client, catalog_rows):
    r = client.patch(
        f"/api/v1/material-prices/{catalog_rows[0]}",
        json={
            "unit_of_measure": "SF",
            "labor_units_per_hour": "30",
            "labor_rate_unit": "SQFT Per Hour",
        },
    )
    assert r.status_code == 200, r.get_json()
    item = r.get_json()["item"]
    assert item["labor_units_per_hour"] == 30
    assert item["labor_rate_unit"] == "SF"
    assert item["labor_per"] == 0.0333
    assert item["unit_of_measure"] == "SF"
    assert item["labor_production"] == "30 SF/hr"

    uom = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": [catalog_rows[1]], "field": "unit_of_measure", "value": "LF"},
    )
    assert uom.status_code == 200, uom.get_json()
    bulk = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": [catalog_rows[1]], "field": "labor_units_per_hour", "value": "8"},
    )
    assert bulk.status_code == 200, bulk.get_json()
    unit = client.post(
        "/api/v1/material-prices/bulk",
        json={"ids": [catalog_rows[1]], "field": "labor_rate_unit", "value": "LF"},
    )
    assert unit.status_code == 200, unit.get_json()
    listed = client.get("/api/v1/material-prices?manufacturer=BulkMfg&limit=50")
    hit = next(x for x in listed.get_json()["items"] if x["id"] == catalog_rows[1])
    assert hit["labor_units_per_hour"] == 8
    assert hit["labor_rate_unit"] == "LF"
    assert hit["labor_per"] == 0.125
    assert hit["unit_of_measure"] == "LF"


def test_patch_sf_rate_converts_ea_not_lf(client, catalog_rows):
    sf = client.patch(
        f"/api/v1/material-prices/{catalog_rows[0]}",
        json={"labor_units_per_hour": "30", "labor_rate_unit": "SF"},
    )
    assert sf.status_code == 200, sf.get_json()
    item = sf.get_json()["item"]
    assert item["unit_of_measure"] == "SF"
    assert item["labor_units_per_hour"] == 30
    assert item["labor_per"] == 0.0333

    lf = client.patch(
        f"/api/v1/material-prices/{catalog_rows[1]}",
        json={
            "unit_of_measure": "EA",
            "labor_per": "0.1667",
            "labor_units_per_hour": "8",
            "labor_rate_unit": "LF",
        },
    )
    assert lf.status_code == 200, lf.get_json()
    kept = lf.get_json()["item"]
    assert kept["unit_of_measure"] == "EA"
    assert kept["labor_per"] == 0.1667
    assert kept["labor_units_per_hour"] is None
    assert kept["labor_rate_unit"] is None


def test_patch_material_price_rejects_blank_item(client, catalog_rows):
    r = client.patch(
        f"/api/v1/material-prices/{catalog_rows[0]}",
        json={"item": ""},
    )
    assert r.status_code == 400


def test_material_price_supplier_link_filter_and_bulk(client, catalog_rows):
    from app.models.company import Company, Contact

    vendor_id = None
    vendor_name = "BuyFrom-" + uuid.uuid4().hex[:6]
    with client.application.app_context():
        vendor = Company(
            name=vendor_name,
            company_type="vendor",
            email="orders@" + vendor_name.lower() + ".example.com",
        )
        db.session.add(vendor)
        db.session.flush()
        db.session.add(
            Contact(
                company_id=vendor.id,
                first_name="Pat",
                last_name="Buyer",
                email="pat@" + vendor_name.lower() + ".example.com",
                is_primary=True,
            )
        )
        db.session.commit()
        vendor_id = str(vendor.id)
    try:
        listed = client.get("/api/v1/material-prices?manufacturer=BulkMfg&limit=50")
        assert listed.status_code == 200
        hit = next(x for x in listed.get_json()["items"] if x["id"] == catalog_rows[0])
        assert hit["supplier_company_id"] is None
        assert hit["supplier_name"] is None
        assert hit["supplier_email"] is None

        patched = client.patch(
            f"/api/v1/material-prices/{catalog_rows[0]}",
            json={"supplier_company_id": vendor_id},
        )
        assert patched.status_code == 200, patched.get_json()
        item = patched.get_json()["item"]
        assert item["supplier_company_id"] == vendor_id
        assert item["supplier_name"] == vendor_name
        assert item["supplier_email"] == "orders@" + vendor_name.lower() + ".example.com"

        by_id = client.get("/api/v1/material-prices?supplier_company_id=" + vendor_id)
        assert by_id.status_code == 200
        ids = {x["id"] for x in by_id.get_json()["items"]}
        assert catalog_rows[0] in ids
        assert catalog_rows[1] not in ids

        by_name = client.get("/api/v1/material-prices?supplier=" + vendor_name)
        assert by_name.status_code == 200
        assert any(x["id"] == catalog_rows[0] for x in by_name.get_json()["items"])

        facets = client.get("/api/v1/material-prices/facets")
        assert facets.status_code == 200
        assert vendor_name in facets.get_json()["suppliers"]

        bulk = client.post(
            "/api/v1/material-prices/bulk",
            json={"ids": catalog_rows, "field": "supplier_company_id", "value": vendor_name},
        )
        assert bulk.status_code == 200, bulk.get_json()
        assert bulk.get_json()["updated_count"] == 2
        assert all(x["supplier_company_id"] == vendor_id for x in bulk.get_json()["updated"])

        cleared = client.patch(
            f"/api/v1/material-prices/{catalog_rows[0]}",
            json={"supplier_company_id": ""},
        )
        assert cleared.status_code == 200, cleared.get_json()
        assert cleared.get_json()["item"]["supplier_company_id"] is None

        missing = client.patch(
            f"/api/v1/material-prices/{catalog_rows[0]}",
            json={"supplier_company_id": "No Such Vendor"},
        )
        assert missing.status_code == 400
    finally:
        with client.application.app_context():
            for mid in catalog_rows:
                row = db.session.get(MaterialPrice, uuid.UUID(mid))
                if row is not None:
                    row.supplier_company_id = None
            company = db.session.get(Company, uuid.UUID(vendor_id))
            if company is not None:
                db.session.delete(company)
            db.session.commit()


def test_material_price_supplier_email_falls_back_to_contact(client, catalog_rows):
    from app.models.company import Company, Contact

    vendor_id = None
    vendor_name = "Inbox-" + uuid.uuid4().hex[:6]
    with client.application.app_context():
        vendor = Company(name=vendor_name, company_type="vendor", email=None)
        db.session.add(vendor)
        db.session.flush()
        db.session.add(
            Contact(
                company_id=vendor.id,
                first_name="Sam",
                last_name="Sales",
                email="sales@" + vendor_name.lower() + ".example.com",
                is_primary=True,
            )
        )
        db.session.commit()
        vendor_id = str(vendor.id)
    try:
        patched = client.patch(
            f"/api/v1/material-prices/{catalog_rows[0]}",
            json={"supplier_company_id": vendor_id},
        )
        assert patched.status_code == 200, patched.get_json()
        assert patched.get_json()["item"]["supplier_email"] == "sales@" + vendor_name.lower() + ".example.com"
    finally:
        with client.application.app_context():
            row = db.session.get(MaterialPrice, uuid.UUID(catalog_rows[0]))
            if row is not None:
                row.supplier_company_id = None
            company = db.session.get(Company, uuid.UUID(vendor_id))
            if company is not None:
                db.session.delete(company)
            db.session.commit()
