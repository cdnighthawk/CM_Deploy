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
