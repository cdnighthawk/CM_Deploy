"""Jinja2 document render routes (HTML purchase order + client proposal)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Company, Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_render_purchase_order_html_and_proposal(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="doc_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Doc", last_name="User")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="DocProj-" + uuid.uuid4().hex[:8], description="Demo scope text for proposal.")
        own = Company(name="OwnerCo " + uuid.uuid4().hex[:6], company_type="owner")
        db.session.add_all([p, own])
        db.session.flush()
        p.owner_company_id = own.id
        v = Company(name="Vendor " + uuid.uuid4().hex[:6], company_type="vendor")
        db.session.add(v)
        db.session.flush()
        pid = str(p.id)
        vid = str(v.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r0 = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "subcontract",
            "vendor_company_id": vid,
            "title": "Sub only",
        },
        headers=hdr,
    )
    assert r0.status_code == 201
    sub_id = r0.get_json()["item"]["id"]

    r_bad = client.get(
        f"/api/v1/projects/{pid}/commitments/{sub_id}/render/purchase-order",
        headers=hdr,
    )
    assert r_bad.status_code == 400

    r1 = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": vid,
            "title": "Lumber PO",
            "reference_number": "PO-9001",
        },
        headers=hdr,
    )
    assert r1.status_code == 201
    po_id = r1.get_json()["item"]["id"]

    client.post(
        f"/api/v1/projects/{pid}/commitments/{po_id}/line-items",
        json={"description": "2x4x8", "quantity": "100", "unit": "EA", "unit_cost": "6.00"},
        headers=hdr,
    )

    r2 = client.get(
        f"/api/v1/projects/{pid}/commitments/{po_id}/render/purchase-order",
        headers=hdr,
    )
    assert r2.status_code == 200
    assert r2.content_type.startswith("text/html")
    body = r2.get_data(as_text=True)
    assert "Purchase Order" in body
    assert "PO-9001" in body
    assert "Lumber PO" in body

    r3 = client.get(f"/api/v1/projects/{pid}/render/client-proposal", headers=hdr)
    assert r3.status_code == 200
    assert "Client proposal" in r3.get_data(as_text=True)
    assert "Demo scope text" in r3.get_data(as_text=True)

    r4 = client.get(
        f"/api/v1/projects/{pid}/render/client-proposal?scope_commitment_id={po_id}",
        headers=hdr,
    )
    assert r4.status_code == 200
    html4 = r4.get_data(as_text=True)
    assert "Pricing reference" in html4
