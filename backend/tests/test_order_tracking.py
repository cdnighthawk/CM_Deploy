"""Order-by from schedule + lead time, supplier confirm, field receive wrappers."""
from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError

from app.api._order_tracking_service import compute_order_by_date
from app.extensions import db
from app.models import Company, Contact, Project, ProjectMember, Role, User, UserRole


def _skip_if_unmigrated(exc: Exception) -> None:
    if isinstance(exc, ProgrammingError) or "does not exist" in str(exc) or "UndefinedColumn" in str(exc):
        pytest.skip("order-tracking columns missing (run flask db upgrade)")
    raise exc


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_compute_order_by_date():
    assert compute_order_by_date(date(2026, 9, 15), 10) == date(2026, 9, 5)
    assert compute_order_by_date(date(2026, 9, 15), None) is None
    assert compute_order_by_date(None, 10) is None


def _setup(client):
    with client.application.app_context():
        try:
            role = db.session.scalar(select(Role).where(Role.code == "standard"))
            if role is None:
                role = Role(code="standard", name="Standard")
                db.session.add(role)
                db.session.flush()
            u = User(email="ord_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Buyer")
            db.session.add(u)
            db.session.flush()
            db.session.add(UserRole(user_id=u.id, role_id=role.id))
            p = Project(name="ORD-" + uuid.uuid4().hex[:8])
            v = Company(name="Vendor " + uuid.uuid4().hex[:6], company_type="vendor")
            db.session.add_all([p, v])
            db.session.flush()
            db.session.add(ProjectMember(user_id=u.id, project_id=p.id))
            contact = Contact(
                company_id=v.id,
                first_name="Sam",
                last_name="Supply",
                email="sam+" + uuid.uuid4().hex[:6] + "@vendor.test",
                is_primary=True,
            )
            db.session.add(contact)
            db.session.flush()
            out = {
                "pid": str(p.id),
                "vid": str(v.id),
                "uid": str(u.id),
                "contact_id": str(contact.id),
            }
            db.session.commit()
        except Exception as exc:
            _skip_if_unmigrated(exc)
    return out


def test_order_by_from_schedule_and_lead_time(client, no_dev_admin, monkeypatch):
    ctx = _setup(client)
    hdr = {"X-Usis-User-Id": ctx["uid"]}
    pid = ctx["pid"]

    sent = []

    def _fake_mail(**kwargs):
        sent.append(kwargs)
        return {"sent": True, "dry_run": False, "error": None}

    monkeypatch.setattr("app.api._order_tracking_service.send_plain_notification_email", _fake_mail)

    sched = client.post(
        f"/api/v1/projects/{pid}/schedule-items",
        json={"title": "Frame install", "start_date": "2026-09-20", "end_date": "2026-09-22"},
        headers=hdr,
    )
    assert sched.status_code == 201, sched.get_data(as_text=True)
    sid = sched.get_json()["item"]["id"]

    created = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": ctx["vid"],
            "vendor_contact_id": ctx["contact_id"],
            "title": "Hollow metal frames",
            "reference_number": "PO-OT-1",
            "lead_time_days": 10,
            "schedule_item_id": sid,
            "line_items": [
                {
                    "description": "HM frame",
                    "quantity": "4",
                    "unit": "EA",
                    "unit_cost": "100",
                    "submittal_release_required": False,
                }
            ],
        },
        headers=hdr,
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    item = created.get_json()["item"]
    cid = item["id"]
    assert item["needed_on_site_date"] == "2026-09-20"
    assert item["order_by_date"] == "2026-09-10"
    assert item["lead_time_days"] == 10
    assert sent == []

    issued = client.post(f"/api/purchase-orders/{cid}/issue", json={}, headers=hdr)
    assert issued.status_code == 200, issued.get_data(as_text=True)
    assert issued.get_json()["item"]["order_by_date"] == "2026-09-10"
    assert len(sent) == 1
    assert "2026-09-10" in sent[0]["body"]

    moved = client.patch(
        f"/api/v1/projects/{pid}/schedule-items/{sid}",
        json={"start_date": "2026-09-25", "end_date": "2026-09-27"},
        headers=hdr,
    )
    assert moved.status_code == 200, moved.get_data(as_text=True)
    assert len(sent) == 2

    board = client.get(f"/api/v1/projects/{pid}/order-board", headers=hdr)
    assert board.status_code == 200, board.get_data(as_text=True)
    rows = board.get_json()["items"]
    assert len(rows) == 1
    assert rows[0]["order_by_date"] == "2026-09-15"
    assert rows[0]["needed_on_site_date"] == "2026-09-25"
    assert rows[0]["supplier_confirm_status"] == "sent"

    conf = client.post(
        f"/api/v1/projects/{pid}/purchase-orders/{cid}/supplier-confirm",
        json={"promised_ship_date": "2026-09-12"},
        headers=hdr,
    )
    assert conf.status_code == 200, conf.get_data(as_text=True)
    assert conf.get_json()["item"]["supplier_confirm_status"] == "confirmed"


def test_field_receivables_deliveries_and_receipt_replay(client, no_dev_admin):
    ctx = _setup(client)
    hdr = {"X-Usis-User-Id": ctx["uid"]}
    pid = ctx["pid"]
    created = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": ctx["vid"],
            "title": "Doors",
            "reference_number": "PO-OT-2",
            "needed_on_site_date": date.today().isoformat(),
            "line_items": [
                {
                    "description": "Door",
                    "quantity": "6",
                    "unit": "EA",
                    "unit_cost": "80",
                    "submittal_release_required": False,
                }
            ],
        },
        headers=hdr,
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    cid = created.get_json()["item"]["id"]
    lid = created.get_json()["line_items"][0]["id"]

    issued = client.post(f"/api/purchase-orders/{cid}/issue", json={}, headers=hdr)
    assert issued.status_code == 200, issued.get_data(as_text=True)

    eta = (date.today() + timedelta(days=3)).isoformat()
    ship = client.post(
        f"/api/purchase-orders/{cid}/shipments",
        json={
            "carrier": "UPS",
            "tracking_number": "1ZORDER",
            "tracking_url": "https://www.ups.com/track?tracknum=1ZORDER",
            "shipment_status": "in_transit",
            "estimated_delivery_date": eta,
            "lines": [{"commitment_line_item_id": lid, "quantity": "6"}],
        },
        headers=hdr,
    )
    assert ship.status_code == 201, ship.get_data(as_text=True)

    rec = client.get(f"/api/v1/projects/{pid}/receivables?due=open", headers=hdr)
    assert rec.status_code == 200, rec.get_data(as_text=True)
    items = rec.get_json()["items"]
    assert any(r["commitment_id"] == cid and r["has_open_qty"] for r in items)

    deliv = client.get(f"/api/v1/projects/{pid}/deliveries", headers=hdr)
    assert deliv.status_code == 200, deliv.get_data(as_text=True)
    drows = deliv.get_json()["items"]
    assert any(r["commitment_id"] == cid and r["shipped"] and r["tracking_number"] == "1ZORDER" for r in drows)

    detail = client.get(f"/api/v1/projects/{pid}/purchase-orders/{cid}/receive", headers=hdr)
    assert detail.status_code == 200, detail.get_data(as_text=True)
    assert detail.get_json()["lines"][0]["qty_open"] == "6.0000" or detail.get_json()["lines"][0]["qty_open"].startswith("6")

    client_id = str(uuid.uuid4())
    payload = {
        "client_id": client_id,
        "condition": "accepted",
        "received_on": date.today().isoformat(),
        "lines": [{"commitment_line_item_id": lid, "quantity": "6"}],
    }
    first = client.post(f"/api/v1/projects/{pid}/purchase-orders/{cid}/receipts", json=payload, headers=hdr)
    assert first.status_code == 201, first.get_data(as_text=True)
    assert first.get_json()["created"] is True
    rid = first.get_json()["id"]

    replay = client.post(f"/api/v1/projects/{pid}/purchase-orders/{cid}/receipts", json=payload, headers=hdr)
    assert replay.status_code == 200, replay.get_data(as_text=True)
    assert replay.get_json()["created"] is False
    assert replay.get_json()["id"] == rid


def test_po_communications_order_notice_and_shipment(client, no_dev_admin, monkeypatch):
    ctx = _setup(client)
    hdr = {"X-Usis-User-Id": ctx["uid"]}
    pid = ctx["pid"]
    monkeypatch.setattr(
        "app.api._order_tracking_service.send_plain_notification_email",
        lambda **kwargs: {"sent": True, "dry_run": False, "error": None},
    )
    created = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": ctx["vid"],
            "vendor_contact_id": ctx["contact_id"],
            "title": "Metal studs",
            "reference_number": "PO-COMM-9",
            "needed_on_site_date": (date.today() + timedelta(days=14)).isoformat(),
            "lead_time_days": 5,
            "line_items": [
                {
                    "description": "Stud",
                    "quantity": "10",
                    "unit": "EA",
                    "unit_cost": "12",
                    "submittal_release_required": False,
                }
            ],
        },
        headers=hdr,
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    cid = created.get_json()["item"]["id"]
    lid = created.get_json()["line_items"][0]["id"]

    issued = client.post(f"/api/purchase-orders/{cid}/issue", json={}, headers=hdr)
    assert issued.status_code == 200, issued.get_data(as_text=True)

    eta = (date.today() + timedelta(days=4)).isoformat()
    ship = client.post(
        f"/api/purchase-orders/{cid}/shipments",
        json={
            "carrier": "FedEx",
            "tracking_number": "FXCOMM",
            "shipment_status": "in_transit",
            "estimated_delivery_date": eta,
            "last_note": "Left dock 7am",
            "lines": [{"commitment_line_item_id": lid, "quantity": "10"}],
        },
        headers=hdr,
    )
    assert ship.status_code == 201, ship.get_data(as_text=True)

    comms = client.get(f"/api/v1/projects/{pid}/commitments/{cid}/communications", headers=hdr)
    assert comms.status_code == 200, comms.get_data(as_text=True)
    body = comms.get_json()
    assert body["entity"] == "purchase_order_communications"
    assert body["item"]["po_number"] == "PO-COMM-9"
    sources = {row["source"] for row in body["items"]}
    assert "shipment" in sources
    assert "correspondence" in sources or "order_notice" in sources
    assert any("FXCOMM" in (row.get("preview") or "") for row in body["items"])
    assert any("PO-COMM-9" in (row.get("subject") or "") for row in body["items"])
