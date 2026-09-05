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
        project = Project(
            name=f"ApJob-{uuid.uuid4().hex[:8]}",
            number=f"AP-{uuid.uuid4().hex[:8]}",
            status="active",
            project_type="commercial",
        )
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
    assert r_sub.get_json()["item"]["can_approve"] is True
    assert r_sub.get_json()["item"]["can_reject"] is True

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

    with flask_app.app_context():
        project = Project(
            name=f"ApSubmit-{uuid.uuid4().hex[:8]}",
            number=f"AP-{uuid.uuid4().hex[:8]}",
            status="active",
            project_type="commercial",
        )
        db.session.add(project)
        db.session.commit()
        project_id = str(project.id)
    r3 = client.post(
        f"/api/v1/ap/invoices/{invoice_id}/submit",
        json={"project_id": project_id, "amount": "12.50"},
        headers=h,
    )
    assert r3.status_code == 200, r3.get_data(as_text=True)
    assert r3.get_json()["item"]["status"] == "pending_approval"
    assert r3.get_json()["item"]["project_id"] == project_id


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


def test_mailbox_sync_requires_graph(client):
    r = client.post("/api/v1/ap/mailbox/sync")
    assert r.status_code == 503
    assert "Graph" in (r.get_json().get("error") or "")


def test_mailbox_sync_cron_secret(client, flask_app, monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    flask_app.config["BC_SYNC_CRON_SECRET"] = "inv-cron-secret"
    monkeypatch.setattr(
        "app.ap._invoice_service.sync_invoice_mailbox",
        lambda **kw: {
            "mailbox": "invoices@gousis.com",
            "created": 1,
            "skipped": 0,
            "scanned": 1,
            "errors": [],
        },
    )
    denied = client.post("/api/v1/ap/mailbox/sync")
    assert denied.status_code == 401
    ok = client.post("/api/v1/ap/mailbox/sync", headers={"X-Cron-Secret": "inv-cron-secret"})
    assert ok.status_code == 200, ok.get_data(as_text=True)
    assert ok.get_json()["item"]["created"] == 1


def test_mailbox_sync_graph_403(client, monkeypatch):
    from app.api._notifications import GraphMailError
    from app.ap import _mailbox as ap_mail

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")

    def boom(**kwargs):
        raise GraphMailError(403, "Access denied")

    monkeypatch.setattr(ap_mail, "list_mailbox_messages", boom)
    r = client.post("/api/v1/ap/mailbox/sync")
    assert r.status_code == 403
    err = r.get_json().get("error") or ""
    assert "Mail.ReadWrite" in err


def test_mailbox_sync_graph_502_is_503(client, monkeypatch):
    from app.api._notifications import GraphMailError
    from app.ap import _mailbox as ap_mail

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")

    def boom(**kwargs):
        raise GraphMailError(502, "Graph GET 502: Bad Gateway")

    monkeypatch.setattr(ap_mail, "list_mailbox_messages", boom)
    r = client.post("/api/v1/ap/mailbox/sync")
    assert r.status_code == 503
    err = r.get_json().get("error") or ""
    assert "Graph could not read the mailbox" in err


def test_mailbox_sync_busy_returns_200(client, monkeypatch):
    from app.ap import _mailbox as ap_mail

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")
    assert ap_mail._SYNC_LOCK.acquire(blocking=False)
    try:
        r = client.post("/api/v1/ap/mailbox/sync")
        assert r.status_code == 200, r.get_data(as_text=True)
        assert r.get_json()["item"]["busy"] is True
    finally:
        ap_mail._SYNC_LOCK.release()


def test_mailbox_sync_caps_new_messages(client, monkeypatch):
    from app.ap import _mailbox as ap_mail

    monkeypatch.setenv("MS_ENTRA_TENANT_ID", "tenant-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_ID", "client-id")
    monkeypatch.setenv("MS_ENTRA_CLIENT_SECRET", "client-secret")
    monkeypatch.setattr(ap_mail, "_sync_limits", lambda *a, **k: (1, 70.0))
    mid1 = "msg-" + uuid.uuid4().hex
    mid2 = "msg-" + uuid.uuid4().hex
    monkeypatch.setattr(
        ap_mail,
        "list_mailbox_messages",
        lambda **kw: {"items": [{"id": mid1}, {"id": mid2}]},
    )

    def fake_detail(*, mailbox, message_id):
        return {
            "id": message_id,
            "subject": f"Invoice {message_id}",
            "from": {"address": "vendor@example.com", "name": "Vendor"},
            "preview": "",
            "body_content": "",
            "attachments": [],
            "received": "2026-09-05T12:00:00Z",
        }

    monkeypatch.setattr(ap_mail, "get_mailbox_message", fake_detail)
    monkeypatch.setattr(ap_mail, "mark_mailbox_message_read", lambda **kw: {"ok": True})
    r = client.post("/api/v1/ap/mailbox/sync")
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["created"] == 1, item
    assert item["truncated"] is True
    assert item["busy"] is False


def test_ingest_uses_original_vendor_on_forwarded_mail(flask_app):
    from decimal import Decimal

    from app.ap._mailbox import ingest_graph_message
    from app.models.vendor_invoice import VendorInvoice

    with flask_app.app_context():
        unique = uuid.uuid4().hex[:8]
        vendor = Company(
            name=f"Accurate Door Solutions {unique}",
            company_type="vendor",
            email=f"billing-{unique}@ddh.net",
        )
        db.session.add(vendor)
        db.session.commit()
        vendor_id = vendor.id
        detail = {
            "id": f"graph-fw-{uuid.uuid4().hex}",
            "subject": f"FW: Invoice 15318 from Accurate Door Solutions {unique}",
            "from": {"address": "charles@gousis.com", "name": "Charles Dossett"},
            "preview": "From: Harmony King <harmony@ddh.net>",
            "body_content": (
                "From: Harmony King &lt;harmony@ddh.net&gt;\n"
                "Sent: Friday, June 5, 2026 7:35 AM\n"
                "Amount Due: $247,711.00\n"
            ),
            "attachments": [],
            "received": "2026-09-05T14:26:18Z",
        }
        invoice = ingest_graph_message(detail, mailbox="invoices@gousis.com")
        db.session.commit()
        assert invoice is not None
        row = db.session.get(VendorInvoice, invoice.id)
        assert row is not None
        assert row.from_email == "harmony@ddh.net"
        assert row.from_name == f"Accurate Door Solutions {unique}"
        assert row.vendor_company_id == vendor_id
        assert row.invoice_number == "15318"
        assert row.amount == Decimal("247711.00")


def test_employee_forward_without_fw_prefix_uses_original_sender(flask_app):
    from app.ap._mailbox import ingest_graph_message
    from app.models.vendor_invoice import VendorInvoice

    with flask_app.app_context():
        detail = {
            "id": f"graph-fw-{uuid.uuid4().hex}",
            "subject": "Invoice 15318 from Accurate Door Solutions, Inc.",
            "from": {"address": "portega@gousis.com", "name": "Pamela Ortega"},
            "preview": "",
            "body_content": (
                "---------- Forwarded message ---------<br>"
                "From: Harmony King &lt;harmony@ddh.net&gt;<br>"
                "Amount Due: $12.00\n"
            ),
            "attachments": [],
            "received": "2026-09-05T15:00:00Z",
        }
        invoice = ingest_graph_message(detail, mailbox="invoices@gousis.com")
        db.session.commit()
        assert invoice is not None
        row = db.session.get(VendorInvoice, invoice.id)
        assert row is not None
        assert row.from_email == "harmony@ddh.net"
        assert row.from_name == "Accurate Door Solutions, Inc."
