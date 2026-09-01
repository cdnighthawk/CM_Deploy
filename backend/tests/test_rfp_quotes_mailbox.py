"""RFP invitations from quotes@gousis.com and inbound quote mailbox ingest."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Company, Contact, Project, Role, User, UserRole
from app.models.rfp import RfpVendorQuote


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _staff(client):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="rfp_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Buyer")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="RFP-" + uuid.uuid4().hex[:8])
        v = Company(
            name="Quote Vendor " + uuid.uuid4().hex[:6],
            company_type="vendor",
            email="quotes.vendor." + uuid.uuid4().hex[:6] + "@example.com",
        )
        db.session.add_all([p, v])
        db.session.flush()
        c = Contact(
            company_id=v.id,
            first_name="Sam",
            last_name="Estimator",
            email=v.email,
            is_primary=True,
        )
        db.session.add(c)
        db.session.commit()
        return {
            "uid": str(u.id),
            "pid": str(p.id),
            "vid": str(v.id),
            "cid": str(c.id),
            "email": v.email,
            "hdr": {"X-Usis-User-Id": str(u.id)},
        }


def test_mailbox_status_defaults_to_quotes(client, no_dev_admin):
    ctx = _staff(client)
    r = client.get("/api/v1/rfps/mailbox", headers=ctx["hdr"])
    assert r.status_code == 200, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["mailbox"] == "quotes@gousis.com"


def test_send_records_invite_without_graph(client, no_dev_admin):
    ctx = _staff(client)
    created = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "title": "Drywall bid package"},
        headers=ctx["hdr"],
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    rfp_id = created.get_json()["item"]["id"]
    mail_tag = created.get_json()["item"]["mail_tag"]
    assert mail_tag

    sent = client.post(
        f"/api/v1/rfps/{rfp_id}/send",
        json={"bidders": [{"company_id": ctx["vid"], "contact_id": ctx["cid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    body = sent.get_json()
    assert body["sends"][0]["ok"] is True
    assert body["sends"][0]["dry_run"] is True
    item = body["item"]
    assert item["status"] == "Sent"
    assert item["quotes_mailbox"] == "quotes@gousis.com"
    assert len(item["quotes"]) == 1
    quote = item["quotes"][0]
    assert quote["invited_email"] == ctx["email"]
    assert quote["sent_from_mailbox"] == "quotes@gousis.com"
    assert quote["invite_token"]
    assert f"[RFP {mail_tag}]" in (client.get(f"/api/v1/rfps/{rfp_id}/email-preview", headers=ctx["hdr"]).get_json()["subject"])


def test_sync_ingests_matching_reply_and_skips_duplicate(client, no_dev_admin, monkeypatch):
    ctx = _staff(client)
    created = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "title": "Electrical package"},
        headers=ctx["hdr"],
    )
    rfp_id = created.get_json()["item"]["id"]
    mail_tag = created.get_json()["item"]["mail_tag"]
    client.post(
        f"/api/v1/rfps/{rfp_id}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )

    msg_id = "graph-msg-rfp-" + uuid.uuid4().hex
    detail = {
        "id": msg_id,
        "from": {"address": ctx["email"], "name": "Sam Estimator"},
        "subject": f"[RFP {mail_tag}] Electrical package",
        "body_content": "<p>Our number is $12,400. Quote attached.</p>",
        "preview": "Our number is $12,400.",
        "received": "2026-08-31T18:00:00Z",
        "attachments": [],
    }

    monkeypatch.setattr("app.api._rfp_quotes_service.mailbox_ready", lambda: True)
    monkeypatch.setattr(
        "app.api._rfp_quotes_service.list_mailbox_messages",
        lambda **kw: {"items": [{"id": msg_id}]},
    )
    monkeypatch.setattr("app.api._rfp_quotes_service.get_mailbox_message", lambda **kw: detail)

    sync = client.post("/api/v1/rfps/mailbox/sync", headers=ctx["hdr"])
    assert sync.status_code == 200, sync.get_data(as_text=True)
    item = sync.get_json()["item"]
    assert item["mailbox"] == "quotes@gousis.com"
    assert item["updated"] == 1
    assert item["created"] == 0

    got = client.get(f"/api/v1/rfps/{rfp_id}", headers=ctx["hdr"])
    quote = got.get_json()["item"]["quotes"][0]
    assert quote["source"] == "email"
    assert quote["received_at"]
    assert "12,400" in (quote["notes"] or "")
    assert got.get_json()["item"]["status"] == "Received"

    again = client.post("/api/v1/rfps/mailbox/sync", headers=ctx["hdr"])
    assert again.get_json()["item"]["skipped"] == 1
    assert again.get_json()["item"]["updated"] == 0

    with client.application.app_context():
        rows = db.session.scalars(select(RfpVendorQuote).where(RfpVendorQuote.graph_inbound_message_id == msg_id)).all()
        assert len(rows) == 1


def test_sync_skips_unmatched_subject(client, no_dev_admin, monkeypatch):
    ctx = _staff(client)
    msg_id = "graph-msg-noise-" + uuid.uuid4().hex
    monkeypatch.setattr("app.api._rfp_quotes_service.mailbox_ready", lambda: True)
    monkeypatch.setattr(
        "app.api._rfp_quotes_service.list_mailbox_messages",
        lambda **kw: {"items": [{"id": msg_id}]},
    )
    monkeypatch.setattr(
        "app.api._rfp_quotes_service.get_mailbox_message",
        lambda **kw: {
            "id": msg_id,
            "from": {"address": "stranger@example.com", "name": "Stranger"},
            "subject": "Lunch tomorrow?",
            "body_content": "Are we still on?",
            "preview": "Are we still on?",
            "received": "2026-08-31T18:00:00Z",
            "attachments": [],
        },
    )
    sync = client.post("/api/v1/rfps/mailbox/sync", headers=ctx["hdr"])
    assert sync.status_code == 200
    assert sync.get_json()["item"]["unmatched"] == 1


def test_portal_invite_token_updates_existing_quote(client, no_dev_admin):
    ctx = _staff(client)
    created = client.post(
        "/api/v1/rfps",
        json={"project_id": ctx["pid"], "title": "Paint package"},
        headers=ctx["hdr"],
    )
    rfp_id = created.get_json()["item"]["id"]
    sent = client.post(
        f"/api/v1/rfps/{rfp_id}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"], "vendor_label": "Quote Vendor"}]},
        headers=ctx["hdr"],
    )
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    page = client.get(f"/public/rfp/{token}")
    assert page.status_code == 200
    assert b"Paint package" in page.data
    posted = client.post(f"/public/rfp/{token}", data={"vendor_label": "Quote Vendor", "notes": "Portal bid 8k"})
    assert posted.status_code == 200
    got = client.get(f"/api/v1/rfps/{rfp_id}", headers=ctx["hdr"])
    quotes = got.get_json()["item"]["quotes"]
    assert len(quotes) == 1
    assert quotes[0]["source"] == "portal"
    assert quotes[0]["notes"] == "Portal bid 8k"
