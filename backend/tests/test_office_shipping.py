"""Named company offices and job shipping destination."""
from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import select

from app.extensions import db
from app.models import Company, CompanyOffice, Project, Role, User, UserRole


def _staff(client):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(
            email="off_" + uuid.uuid4().hex[:8] + "@t.com",
            first_name="Pat",
            last_name="Office",
            is_superuser=True,
        )
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(
            name="Ship-job-" + uuid.uuid4().hex[:8],
            address_line1="100 Jobsite Way",
            city="San Diego",
            state="CA",
            postal_code="92101",
        )
        db.session.add(p)
        self_companies = list(
            db.session.scalars(
                select(Company)
                .where(Company.company_type == "self", Company.deleted_at.is_(None))
                .order_by(Company.created_at.asc())
            ).all()
        )
        office_ids = []
        for self_co in self_companies:
            office_ids.extend(
                [
                    o.id
                    for o in db.session.scalars(
                        select(CompanyOffice).where(CompanyOffice.company_id == self_co.id)
                    ).all()
                ]
            )
        if office_ids:
            for proj in db.session.scalars(
                select(Project).where(Project.ship_to_office_id.in_(office_ids))
            ).all():
                proj.ship_to_office_id = None
            for oid in office_ids:
                row = db.session.get(CompanyOffice, oid)
                if row is not None:
                    db.session.delete(row)
        db.session.commit()
        return {"uid": str(u.id), "pid": str(p.id), "hdr": {"X-Usis-User-Id": str(u.id)}}


def test_create_list_office_and_project_shipping(client, monkeypatch):
    monkeypatch.setattr(
        "app.api._office_location.geocode_us_address",
        lambda query: (33.1192, -117.0864),
    )
    ctx = _staff(client)
    created = client.post(
        "/api/v1/office-locations",
        json={
            "name": "Escondido shop",
            "address_line1": "123 Main St",
            "city": "Escondido",
            "state": "CA",
            "postal_code": "92025",
            "is_default": True,
        },
        headers=ctx["hdr"],
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    office = created.get_json()["item"]
    assert office["name"] == "Escondido shop"
    assert office["is_default"] is True
    assert "Escondido" in office["address"]

    listed = client.get("/api/v1/office-locations", headers=ctx["hdr"])
    assert listed.status_code == 200
    ids = {x["id"] for x in listed.get_json()["items"]}
    assert office["id"] in ids

    patched = client.patch(
        f"/api/v1/projects/{ctx['pid']}",
        json={
            "expected_install_date": "2026-10-15",
            "ship_to_kind": "office",
            "ship_to_office_id": office["id"],
        },
        headers=ctx["hdr"],
    )
    assert patched.status_code == 200, patched.get_data(as_text=True)
    item = patched.get_json()["item"]
    assert item["expected_install_date"] == "2026-10-15"
    assert item["ship_to_kind"] == "office"
    assert item["ship_to_office_id"] == office["id"]
    ship = item["job_shipping"]
    assert ship["ship_to_kind"] == "office"
    assert "Escondido" in (ship["shipping_address"] or "")
    assert ship["expected_install_date"] == "2026-10-15"

    jobsite = client.patch(
        f"/api/v1/projects/{ctx['pid']}",
        json={"ship_to_kind": "jobsite"},
        headers=ctx["hdr"],
    )
    assert jobsite.status_code == 200
    ship = jobsite.get_json()["item"]["job_shipping"]
    assert ship["ship_to_kind"] == "jobsite"
    assert "Jobsite" in (ship["shipping_label"] or "")
    assert "San Diego" in (ship["shipping_address"] or "")


def test_rfp_exposes_and_updates_job_shipping(client, monkeypatch):
    monkeypatch.setattr(
        "app.api._office_location.geocode_us_address",
        lambda query: (33.1192, -117.0864),
    )
    ctx = _staff(client)
    office = client.post(
        "/api/v1/office-locations",
        json={"name": "Yard", "city": "Escondido", "state": "CA", "postal_code": "92025", "is_default": True},
        headers=ctx["hdr"],
    ).get_json()["item"]

    rfp = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "title": "Lockers", "scope_of_work": "Price lockers."},
        headers=ctx["hdr"],
    )
    assert rfp.status_code == 201, rfp.get_data(as_text=True)
    rid = rfp.get_json()["item"]["id"]
    ship = rfp.get_json()["item"]["job_shipping"]
    assert ship["ship_to_kind"] == "jobsite"

    updated = client.patch(
        f"/api/v1/rfps/{rid}/job-shipping",
        json={
            "ship_to_kind": "office",
            "ship_to_office_id": office["id"],
            "expected_install_date": "2026-11-01",
        },
        headers=ctx["hdr"],
    )
    assert updated.status_code == 200, updated.get_data(as_text=True)
    ship = updated.get_json()["item"]["job_shipping"]
    assert ship["ship_to_kind"] == "office"
    assert ship["expected_install_date"] == "2026-11-01"
    preview = client.get(f"/api/v1/rfps/{rid}/email-preview", headers=ctx["hdr"])
    assert preview.status_code == 200
    html = preview.get_json().get("html") or ""
    assert "Ship to" in html
    assert "Expected install date" in html

    with client.application.app_context():
        p = db.session.get(Project, uuid.UUID(ctx["pid"]))
        assert p.expected_install_date == date(2026, 11, 1)
        assert p.ship_to_kind == "office"
        assert str(p.ship_to_office_id) == office["id"]


def test_delete_office_clears_default(client, monkeypatch):
    monkeypatch.setattr(
        "app.api._office_location.geocode_us_address",
        lambda query: (33.1192, -117.0864),
    )
    ctx = _staff(client)
    a = client.post(
        "/api/v1/office-locations",
        json={"name": "A", "city": "Escondido", "state": "CA", "postal_code": "92025", "is_default": True},
        headers=ctx["hdr"],
    ).get_json()["item"]
    b = client.post(
        "/api/v1/office-locations",
        json={"name": "B", "city": "San Marcos", "state": "CA", "postal_code": "92069"},
        headers=ctx["hdr"],
    ).get_json()["item"]
    gone = client.delete(f"/api/v1/office-locations/{a['id']}", headers=ctx["hdr"])
    assert gone.status_code == 200, gone.get_data(as_text=True)
    listed = client.get("/api/v1/office-locations", headers=ctx["hdr"]).get_json()["items"]
    ids = {x["id"]: x for x in listed}
    assert a["id"] not in ids, listed
    assert b["id"] in ids, listed
    assert ids[b["id"]]["is_default"] is True, listed
    with client.application.app_context():
        assert db.session.get(CompanyOffice, uuid.UUID(a["id"])) is None
        self_co = db.session.scalar(select(Company).where(Company.company_type == "self"))
        assert self_co is not None
