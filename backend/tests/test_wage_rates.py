"""Wage rate catalog list / create / import / patch / delete."""
from __future__ import annotations

import uuid


def test_wage_rates_crud_and_import(client):
    tag = uuid.uuid4().hex[:8]
    state = f"ZZ-{tag}"
    client.put(
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
    created = client.post(
        "/api/v1/wage-rates",
        json={
            "state": state,
            "sub_area": "Clark",
            "year": 2099,
            "trade": f"Laborer {tag}",
            "basic_hourly_rate": "41.5",
            "health_welfare": "8.25",
            "pension": "6",
        },
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    item = created.get_json()["item"]
    assert item["state"] == state
    assert item["sub_area"] == "Clark"
    assert item["year"] == 2099
    assert item["basic_hourly_rate"] == 41.5
    assert item["fringe_hourly"] == 55.75
    assert item["total_loaded_hourly"] == 59.1738
    assert item["burden_hourly"] == 3.4238
    row_id = item["id"]

    listed = client.get(f"/api/v1/wage-rates?limit=50&q={tag}")
    assert listed.status_code == 200
    body = listed.get_json()
    assert body["entity"] == "wage_rates"
    assert body["total"] >= 1
    ids = {r["id"] for r in body["items"]}
    assert row_id in ids

    patched = client.patch(
        f"/api/v1/wage-rates/{row_id}",
        json={"basic_hourly_rate": "42", "notes": "updated"},
    )
    assert patched.status_code == 200, patched.get_data(as_text=True)
    assert patched.get_json()["item"]["basic_hourly_rate"] == 42
    assert patched.get_json()["item"]["notes"] == "updated"

    duplicate = client.post(
        "/api/v1/wage-rates",
        json={"state": state, "sub_area": "Clark", "year": 2099, "trade": f"Laborer {tag}"},
    )
    assert duplicate.status_code == 409

    csv_text = (
        "state,sub_area,year,trade,basic_hourly_rate,health_welfare,pension,"
        "vacation_holiday,other_payments,training,notes\n"
        f"{state},Los Angeles,2098,Carpenter {tag},55.25,10.10,8.50,3.00,1.00,0.80,\n"
        f"{state},Los Angeles,2098,Electrician {tag},62.00,12.00,9.25,3.50,0.00,1.10,assumed\n"
    )
    imported = client.post("/api/v1/wage-rates/import", json={"csv": csv_text})
    assert imported.status_code == 200, imported.get_data(as_text=True)
    result = imported.get_json()
    assert result["created"] == 2
    assert result["total"] == 2

    again = client.post("/api/v1/wage-rates/import", json={"csv": csv_text})
    assert again.status_code == 200
    assert again.get_json()["updated"] == 2
    assert again.get_json()["created"] == 0

    facets = client.get("/api/v1/wage-rates/facets")
    assert facets.status_code == 200
    facet_body = facets.get_json()
    assert state in facet_body["states"]
    assert 2098 in facet_body["years"]
    assert f"Electrician {tag}" in facet_body["trades"]

    assumed = client.get(
        f"/api/v1/wage-rates?limit=20&state={state}&year=2098&trade=Electrician%20{tag}"
    )
    assert assumed.status_code == 200
    items = assumed.get_json()["items"]
    assert items
    assert items[0]["is_assumed"] is True

    deleted = client.delete(f"/api/v1/wage-rates/{row_id}")
    assert deleted.status_code == 200
    missing = client.get(f"/api/v1/wage-rates/{row_id}")
    assert missing.status_code == 404

    burden_get = client.get("/api/v1/wage-rates/burden")
    assert burden_get.status_code == 200
    burden = burden_get.get_json()["burden"]
    assert burden["social_security_pct"] == 6.2
    assert burden["medicare_pct"] == 1.45
    assert burden["futa_pct"] == 0.6

    saved = client.put(
        "/api/v1/wage-rates/burden",
        json={"suta_pct": "3.4", "workers_comp_pct": "12", "other_pct": "1.5"},
    )
    assert saved.status_code == 200, saved.get_data(as_text=True)
    saved_burden = saved.get_json()["burden"]
    assert saved_burden["suta_pct"] == 3.4
    assert saved_burden["workers_comp_pct"] == 12
    assert saved_burden["social_security_pct"] == 6.2

    wc_row = client.post(
        "/api/v1/wage-rates",
        json={
            "state": state,
            "sub_area": "Orange",
            "year": 2097,
            "trade": f"Glazier {tag}",
            "basic_hourly_rate": "50",
            "workers_comp_pct": "8",
        },
    )
    assert wc_row.status_code == 201, wc_row.get_data(as_text=True)
    wc_item = wc_row.get_json()["item"]
    assert wc_item["workers_comp_pct"] == 8
    wc_line = next(line for line in wc_item["burden_lines"] if line["key"] == "workers_comp_pct")
    assert wc_line["pct"] == 8
    assert wc_line["amount"] == 4
    client.put(
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
