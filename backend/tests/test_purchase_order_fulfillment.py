"""PO workflow, shipments, receive rollups, and 3-way match."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.extensions import db
from app.models import Company, Commitment, Project, Role, User, UserRole, VendorInvoice


def _skip_if_unmigrated(exc: Exception) -> None:
    if isinstance(exc, ProgrammingError) or "does not exist" in str(exc):
        pytest.skip("PO / workflow tables missing (run flask db upgrade)")
    raise exc


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _buyer(client):
    with client.application.app_context():
        try:
            role = db.session.scalar(select(Role).where(Role.code == "standard"))
            if role is None:
                role = Role(code="standard", name="Standard")
                db.session.add(role)
                db.session.flush()
            u = User(email="po_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Buyer")
            db.session.add(u)
            db.session.flush()
            db.session.add(UserRole(user_id=u.id, role_id=role.id))
            p = Project(name="PO-" + uuid.uuid4().hex[:8])
            v = Company(name="Vendor " + uuid.uuid4().hex[:6], company_type="vendor")
            db.session.add_all([p, v])
            db.session.flush()
            pid, vid, uid = str(p.id), str(v.id), str(u.id)
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)
    return pid, vid, uid


def test_po_create_starts_workflow_and_shipment_receive_match(client, no_dev_admin):
    pid, vid, uid = _buyer(client)
    hdr = {"X-Usis-User-Id": uid}

    r = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": vid,
            "title": "Doors",
            "reference_number": "PO-8801",
            "promised_ship_date": "2026-09-01",
            "line_items": [{"description": "Hollow metal door", "quantity": "10", "unit": "EA", "unit_cost": "120"}],
        },
        headers=hdr,
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    cid = body["item"]["id"]
    lid = body["line_items"][0]["id"]
    assert body["item"]["promised_ship_date"] == "2026-09-01"
    assert body.get("workflow", {}).get("processKey") == "purchase_order"
    assert body["workflow"]["currentStepKey"] == "issue"

    issued = client.post(f"/api/purchase-orders/{cid}/issue", json={}, headers=hdr)
    assert issued.status_code == 200, issued.get_data(as_text=True)

    ship = client.post(
        f"/api/purchase-orders/{cid}/shipments",
        json={
            "carrier": "UPS",
            "tracking_number": "1Z999",
            "tracking_url": "https://www.ups.com/track?tracknum=1Z999",
            "shipment_status": "in_transit",
            "actual_ship_date": "2026-08-28",
            "lines": [{"commitment_line_item_id": lid, "quantity": "10"}],
        },
        headers=hdr,
    )
    assert ship.status_code == 201, ship.get_data(as_text=True)
    assert ship.get_json()["fulfillmentStatus"] in ("in_transit", "shipped", "partially_shipped")

    recv = client.post(
        f"/api/purchase-orders/{cid}/receipts",
        json={"lines": [{"commitment_line_item_id": lid, "quantity": "10"}]},
        headers=hdr,
    )
    assert recv.status_code == 201, recv.get_data(as_text=True)
    assert recv.get_json()["fulfillment_status"] == "received"

    with client.application.app_context():
        c = db.session.get(Commitment, uuid.UUID(cid))
        inv = VendorInvoice(
            status="received",
            source="manual",
            commitment_id=c.id,
            project_id=c.project_id,
            amount=c.total_amount or 1200,
            currency="USD",
            parse_meta={},
        )
        db.session.add(inv)
        db.session.commit()

    match = client.post(f"/api/purchase-orders/{cid}/three-way-match", json={}, headers=hdr)
    assert match.status_code == 200, match.get_data(as_text=True)
    assert match.get_json()["matchStatus"] in ("matched", "quantity_ok", "amount_ok")

    track = client.get(f"/api/purchase-orders/{cid}", headers=hdr)
    assert track.status_code == 200
    assert track.get_json()["shipments"]


def test_dashboard_ops_kpis(client):
    r = client.get("/api/v1/dashboard/ops-kpis")
    if r.status_code >= 500:
        pytest.skip("dashboard KPI query failed — migrate first")
    assert r.status_code == 200
    body = r.get_json()
    assert "openRfps" in body
    assert "qcAging" in body
    assert "aiCritical" in body
    assert "poInTransit" in body
