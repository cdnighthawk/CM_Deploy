"""Vendor invoice intake, job routing, and payment approval API."""
from __future__ import annotations

import io
import uuid

from sqlalchemy import select

from app.extensions import db
from app.models import Company, Project, Role, User, UserRole
from app.models.vendor_invoice import VendorInvoice


def _headers(user_id: str) -> dict[str, str]:
    return {"X-Usis-User-Id": user_id, "Accept": "application/json"}


def test_vendor_invoice_full_workflow(client, flask_app):
    with flask_app.app_context():
        project = Project(name=f"ApJob-{uuid.uuid4().hex[:8]}", number="24-018", status="active", project_type="commercial")
        vendor = Company(name=f"ApVendor-{uuid.uuid4().hex[:6]}", company_type="vendor")
        accountant = User(
            email=f"ap_acct_{uuid.uuid4().hex[:8]}@usis.local",
            first_name="Pat",
            last_name="Accountant",
            is_active=True,
            is_superuser=True,
        )
        db.session.add_all([project, vendor, accountant])
        db.session.flush()
        role = db.session.scalar(select(Role).where(Role.code == "project_accountant"))
        if role is None:
            role = Role(code="project_accountant", name="Project Accountant")
            db.session.add(role)
            db.session.flush()
        db.session.add(UserRole(user_id=accountant.id, role_id=role.id))
        db.session.commit()
        ids = {
            "project_id": str(project.id),
            "vendor_id": str(vendor.id),
            "user_id": str(accountant.id),
        }

    h = _headers(ids["user_id"])
    r = client.post("/api/v1/ap/invoices", json={"from_name": "Supply Co", "subject": "Invoice 1001"}, headers=h)
    assert r.status_code == 200, r.get_data(as_text=True)
    invoice_id = r.get_json()["item"]["id"]
    assert r.get_json()["item"]["status"] == "received"

    r2 = client.patch(
        f"/api/v1/ap/invoices/{invoice_id}",
        json={
            "vendor_company_id": ids["vendor_id"],
            "project_id": ids["project_id"],
            "invoice_number": "1001",
            "amount": "250.00",
        },
        headers=h,
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()["item"]["status"] == "routed"
    assert r2.get_json()["item"]["project_id"] == ids["project_id"]

    data = {"file": (io.BytesIO(b"%PDF-1.4 fake"), "bill.pdf")}
    r_up = client.post(
        f"/api/v1/ap/invoices/{invoice_id}/files",
        data=data,
        content_type="multipart/form-data",
        headers={"X-Usis-User-Id": ids["user_id"]},
    )
    assert r_up.status_code == 200, r_up.get_data(as_text=True)
    assert r_up.get_json()["item"]["files"]

    r_sub = client.post(f"/api/v1/ap/invoices/{invoice_id}/submit", headers=h)
    assert r_sub.status_code == 200
    assert r_sub.get_json()["item"]["status"] == "pending_approval"

    r_queue = client.get("/api/v1/ap/invoices/approvals", headers=h)
    assert r_queue.status_code == 200
    assert invoice_id in [row["id"] for row in r_queue.get_json().get("items") or []]

    r_ok = client.post(f"/api/v1/ap/invoices/{invoice_id}/approve", headers=h)
    assert r_ok.status_code == 200
    assert r_ok.get_json()["item"]["status"] == "approved"

    r_paid = client.post(
        f"/api/v1/ap/invoices/{invoice_id}/mark-paid",
        json={"payment_ref": "CHK-88"},
        headers=h,
    )
    assert r_paid.status_code == 200
    assert r_paid.get_json()["item"]["status"] == "paid"
    assert r_paid.get_json()["item"]["payment_ref"] == "CHK-88"

    with flask_app.app_context():
        row = db.session.get(VendorInvoice, uuid.UUID(invoice_id))
        assert row is not None
        assert row.paid_at is not None


def test_submit_requires_job_and_amount(client, flask_app):
    with flask_app.app_context():
        user = User(
            email=f"ap_user_{uuid.uuid4().hex[:8]}@usis.local",
            first_name="Office",
            last_name="Coord",
            is_active=True,
            is_superuser=True,
        )
        db.session.add(user)
        db.session.commit()
        uid = str(user.id)
    h = _headers(uid)
    r = client.post("/api/v1/ap/invoices", json={"subject": "Missing job"}, headers=h)
    assert r.status_code == 200
    invoice_id = r.get_json()["item"]["id"]
    r2 = client.post(f"/api/v1/ap/invoices/{invoice_id}/submit", headers=h)
    assert r2.status_code == 400
    assert "job" in (r2.get_json().get("error") or "").lower()


def test_reject_requires_reason(client, flask_app):
    with flask_app.app_context():
        project = Project(name=f"ApJob2-{uuid.uuid4().hex[:8]}", status="active", project_type="commercial")
        user = User(
            email=f"ap_mgr_{uuid.uuid4().hex[:8]}@usis.local",
            first_name="Maya",
            last_name="Manager",
            is_active=True,
            is_superuser=True,
        )
        db.session.add_all([project, user])
        db.session.commit()
        ids = {"project_id": str(project.id), "user_id": str(user.id)}
    h = _headers(ids["user_id"])
    r = client.post("/api/v1/ap/invoices", json={"amount": "10.00", "project_id": ids["project_id"]}, headers=h)
    assert r.status_code == 200
    invoice_id = r.get_json()["item"]["id"]
    r_sub = client.post(f"/api/v1/ap/invoices/{invoice_id}/submit", headers=h)
    assert r_sub.status_code == 200
    r_bad = client.post(f"/api/v1/ap/invoices/{invoice_id}/reject", json={}, headers=h)
    assert r_bad.status_code == 400
    r_ok = client.post(f"/api/v1/ap/invoices/{invoice_id}/reject", json={"reason": "Wrong job"}, headers=h)
    assert r_ok.status_code == 200
    assert r_ok.get_json()["item"]["status"] == "rejected"
