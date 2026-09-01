"""Company-wide cost codes; project JCCs populate from takeoff."""
from __future__ import annotations

import uuid

from app.extensions import db
from app.models import Project


def test_company_cost_codes_and_takeoff_sync(client):
    code = "CC-" + uuid.uuid4().hex[:8]
    created = client.post(
        "/api/v1/cost-codes",
        json={"code": code, "description": "Concrete", "units": "CY", "order_number": 10},
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    item = created.get_json()["item"]
    assert item["code"] == code
    assert item["description"] == "Concrete"
    assert item["units"] == "CY"

    listed = client.get("/api/v1/cost-codes")
    assert listed.status_code == 200
    codes = {r["code"] for r in listed.get_json()["items"]}
    assert code in codes

    with client.application.app_context():
        p = Project(name="JCC-TO-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    blocked = client.post(
        f"/api/v1/projects/{pid}/rfi-lookups/cost_codes",
        json={"code": "99-999", "description": "Should not add"},
    )
    assert blocked.status_code == 400

    empty = client.get(f"/api/v1/projects/{pid}/rfi-lookups/cost_codes")
    assert empty.status_code == 200
    assert empty.get_json()["items"] == []

    line = client.post(
        f"/api/v1/projects/{pid}/takeoff-lines",
        json={
            "description": "Footings",
            "quantity": 12,
            "unit": "CY",
            "job_cost_code": code,
        },
    )
    assert line.status_code == 201, line.get_data(as_text=True)
    assert line.get_json()["item"]["job_cost_code_description"] == "Concrete"

    job = client.get(f"/api/v1/projects/{pid}/rfi-lookups/cost_codes")
    assert job.status_code == 200
    rows = job.get_json()["items"]
    assert len(rows) == 1
    assert rows[0]["code"] == code
    assert rows[0]["description"] == "Concrete"
    assert rows[0]["quantity"] == 12
    assert rows[0]["takeoff_line_count"] == 1
    assert rows[0]["in_company_list"] is True


CSI_IMPORT_CSV = """Code,Title,Level
ZZ 00 00,Test Division,1
ZZ 10 00,Test Major,2
ZZ 11 00,Test Minor,3
ZZ 11 13,Test Subminor,3
"""


def test_import_csi_company_cost_codes(client):
    imported = client.post("/api/v1/cost-codes/import", json={"csv": CSI_IMPORT_CSV})
    assert imported.status_code == 200, imported.get_data(as_text=True)
    body = imported.get_json()
    assert body["total"] == 4
    assert body["created"] + body["updated"] == 4

    listed = client.get("/api/v1/cost-codes")
    assert listed.status_code == 200
    by_code = {r["code"]: r for r in listed.get_json()["items"]}
    assert "ZZ 00 00" in by_code
    assert by_code["ZZ 00 00"]["description"] == "Test Division"
    assert by_code["ZZ 00 00"]["division_code"] == "ZZ 00 00"
    assert by_code["ZZ 10 00"]["major_code"] == "ZZ 10 00"
    assert by_code["ZZ 10 00"]["division_desc"] == "Test Division"
    assert by_code["ZZ 11 00"]["minor_code"] == "ZZ 11 00"
    assert by_code["ZZ 11 00"]["major_desc"] == "Test Major"
    assert by_code["ZZ 11 13"]["subminor_code"] == "ZZ 11 13"
    assert by_code["ZZ 11 13"]["minor_code"] == "ZZ 11 00"
    assert by_code["ZZ 11 13"]["minor_desc"] == "Test Minor"

    again = client.post("/api/v1/cost-codes/import", json={"csv": CSI_IMPORT_CSV})
    assert again.status_code == 200
    assert again.get_json()["created"] == 0
    assert again.get_json()["updated"] == 4

    for row in by_code.values():
        if str(row.get("code") or "").startswith("ZZ "):
            deleted = client.delete(f"/api/v1/cost-codes/{row['id']}")
            assert deleted.status_code == 200
