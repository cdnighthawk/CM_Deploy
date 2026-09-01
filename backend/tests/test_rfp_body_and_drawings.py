"""RFP body (takeoff / manual / narrative) and drawing send path."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import BytesIO

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import (
    Commitment,
    Company,
    Contact,
    Drawing,
    Estimate,
    EstimateLineItem,
    Project,
    Role,
    RfpVendorQuote,
    TakeoffLineItem,
    User,
    UserRole,
)


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _due():
    return (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()


def _staff(client, *, vendor_email=True):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="rfp_b_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Buyer")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="RFP-body-" + uuid.uuid4().hex[:8])
        v = Company(
            name="Quote Vendor " + uuid.uuid4().hex[:6],
            company_type="vendor",
            email=("quotes.vendor." + uuid.uuid4().hex[:6] + "@example.com") if vendor_email else None,
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


def _create_rfp(client, ctx, **extra):
    body = {"project_id": ctx["pid"], "title": extra.pop("title", "Package"), "due_at": _due()}
    body.update(extra)
    r = client.post("/api/v1/rfps", json=body, headers=ctx["hdr"])
    assert r.status_code == 201, r.get_data(as_text=True)
    return r.get_json()["item"]


def test_narrative_only_send_and_lump_sum_portal(client, no_dev_admin):
    ctx = _staff(client)
    item = _create_rfp(
        client,
        ctx,
        title="Lump sum finishes",
        line_source="narrative",
        scope_of_work="Install corridor finishes per finish schedule.",
        inclusions="Material and labor",
        exclusions="Flooring",
    )
    assert item["line_source"] == "narrative"
    preview = client.get(f"/api/v1/rfps/{item['id']}/email-preview", headers=ctx["hdr"])
    assert preview.status_code == 200
    assert preview.get_json()["from"] == "quotes@gousis.com"
    assert "corridor finishes" in (preview.get_json()["text"] or "")
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    page = client.get(f"/public/rfp/{token}")
    assert page.status_code == 200
    assert b"Lump sum" in page.data
    assert b"unit_cost" not in page.data.lower()
    posted = client.post(
        f"/public/rfp/{token}",
        data={"vendor_label": "Quote Vendor", "lump_sum_amount": "12400", "vendor_exclusions": "Overtime"},
    )
    assert posted.status_code == 200
    got = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"])
    quote = got.get_json()["item"]["quotes"][0]
    assert quote["lump_sum_amount"] == 12400
    cmp = client.get(f"/api/v1/rfps/{item['id']}/compare", headers=ctx["hdr"])
    rows = cmp.get_json()["item"]["rows"]
    assert len(rows) == 1
    assert rows[0]["description"].startswith("Lump sum")


def test_takeoff_attach_omits_costs(client, no_dev_admin):
    ctx = _staff(client)
    with client.application.app_context():
        est = Estimate(project_id=uuid.UUID(ctx["pid"]), name="Takeoff A", status="draft")
        db.session.add(est)
        db.session.flush()
        tl = TakeoffLineItem(
            project_id=uuid.UUID(ctx["pid"]),
            estimate_id=est.id,
            description="GWB partitions",
            quantity=Decimal("120"),
            unit="LF",
            unit_cost=Decimal("18.50"),
            extended_total=Decimal("2220"),
            section="09 21 00",
            takeoff_location="Corridor",
            notes="Level 2",
        )
        db.session.add(tl)
        db.session.commit()
        eid = str(est.id)
        tid = str(tl.id)
    item = _create_rfp(client, ctx, title="Drywall", line_source="takeoff")
    attached = client.post(
        f"/api/v1/rfps/{item['id']}/attach-takeoff",
        json={"estimate_id": eid, "takeoff_line_ids": [tid]},
        headers=ctx["hdr"],
    )
    assert attached.status_code == 200, attached.get_data(as_text=True)
    lines = attached.get_json()["item"]["line_items"]
    assert len(lines) == 1
    assert lines[0]["description"] == "GWB partitions"
    assert lines[0]["quantity"] == 120
    assert "unit_cost" not in lines[0]
    assert lines[0]["source_kind"] == "takeoff"
    blob = str(attached.get_json())
    assert "18.50" not in blob
    assert "2220" not in blob
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    page = client.get(f"/public/rfp/{token}")
    assert b"GWB partitions" in page.data
    assert b"18.50" not in page.data
    frozen = client.patch(
        f"/api/v1/rfps/{item['id']}",
        json={"scope_of_work": "should fail"},
        headers=ctx["hdr"],
    )
    assert frozen.status_code == 400


def test_manual_line_and_missing_email_blocks_send(client, no_dev_admin):
    ctx = _staff(client)
    missing = _staff(client, vendor_email=False)
    item = _create_rfp(client, ctx, title="Custom list", line_source="manual")
    add = client.post(
        f"/api/v1/rfps/{item['id']}/line-items",
        json={"description": "Misc metal", "quantity": 4, "unit": "EA"},
        headers=ctx["hdr"],
    )
    assert add.status_code == 201
    blocked = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": missing["vid"]}]},
        headers=ctx["hdr"],
    )
    assert blocked.status_code == 400
    assert "email" in (blocked.get_json().get("error") or "").lower()
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200


def test_award_writes_takeoff_vendor_quote(client, no_dev_admin):
    ctx = _staff(client)
    with client.application.app_context():
        est = Estimate(project_id=uuid.UUID(ctx["pid"]), name="Award est", status="draft")
        db.session.add(est)
        db.session.flush()
        tl = TakeoffLineItem(
            project_id=uuid.UUID(ctx["pid"]),
            estimate_id=est.id,
            description="ACT ceiling",
            quantity=Decimal("10"),
            unit="SF",
            unit_cost=Decimal("5"),
            extended_total=Decimal("50"),
        )
        db.session.add(tl)
        db.session.flush()
        eli = EstimateLineItem(estimate_id=est.id, takeoff_line_item_id=tl.id, unit_cost=Decimal("5"))
        db.session.add(eli)
        db.session.commit()
        eid = str(est.id)
        tid = str(tl.id)
        eli_id = eli.id
    item = _create_rfp(client, ctx, title="Ceiling", line_source="takeoff")
    client.post(
        f"/api/v1/rfps/{item['id']}/attach-takeoff",
        json={"estimate_id": eid, "takeoff_line_ids": [tid]},
        headers=ctx["hdr"],
    )
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    line_id = sent.get_json()["item"]["visible_line_items"][0]["id"]
    client.post(f"/public/rfp/{token}", data={"vendor_label": "V", f"price_{line_id}": "9.25"})
    quote_id = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"]).get_json()["item"]["quotes"][0]["id"]
    awarded = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": quote_id},
        headers=ctx["hdr"],
    )
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    body = awarded.get_json()["item"]
    assert body["status"] == "Awarded"
    assert body["awarded_quote_id"] == quote_id
    cmt = body["commitment"]
    assert cmt is not None
    assert cmt["reference_number"] == "PO-001"
    assert cmt["status"] == "draft"
    assert cmt["project_id"] == ctx["pid"]
    with client.application.app_context():
        row = db.session.get(EstimateLineItem, eli_id)
        assert row is not None
        assert row.vendor_quote == Decimal("9.25")
        po = db.session.get(Commitment, uuid.UUID(cmt["id"]))
        assert po is not None
        assert po.rfp_id == uuid.UUID(item["id"])
        assert po.vendor_company_id == uuid.UUID(ctx["vid"])
        assert po.commitment_kind == "purchase_order"
        lines = list(po.line_items)
        assert len(lines) == 1
        assert lines[0].unit_cost == Decimal("9.25")
        assert lines[0].quantity == Decimal("10")
        assert lines[0].rfp_line_item_id is not None
        assert str(lines[0].takeoff_line_item_id) == tid
        assert lines[0].estimate_line_item_id == eli_id
    again = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": quote_id},
        headers=ctx["hdr"],
    )
    assert again.status_code == 200, again.get_data(as_text=True)
    assert again.get_json()["item"]["commitment"]["id"] == cmt["id"]
    got = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"])
    assert got.get_json()["item"]["awarded_quote_id"] == quote_id
    assert got.get_json()["item"]["commitment"]["id"] == cmt["id"]


def test_award_lump_sum_creates_ls_po_line(client, no_dev_admin):
    ctx = _staff(client)
    item = _create_rfp(
        client,
        ctx,
        title="Lump sum finishes",
        line_source="narrative",
        scope_of_work="Install corridor finishes per finish schedule.",
    )
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    posted = client.post(
        f"/public/rfp/{token}",
        data={"vendor_label": "Quote Vendor", "lump_sum_amount": "12400", "vendor_exclusions": "Overtime"},
    )
    assert posted.status_code == 200
    quote_id = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"]).get_json()["item"]["quotes"][0]["id"]
    awarded = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": quote_id},
        headers=ctx["hdr"],
    )
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    cmt = awarded.get_json()["item"]["commitment"]
    with client.application.app_context():
        po = db.session.get(Commitment, uuid.UUID(cmt["id"]))
        assert po is not None
        lines = list(po.line_items)
        assert len(lines) == 1
        assert lines[0].unit == "LS"
        assert lines[0].quantity == Decimal("1")
        assert lines[0].unit_cost == Decimal("12400")
        assert "Overtime" in (po.notes or "")


def test_award_requires_project(client, no_dev_admin):
    ctx = _staff(client)
    item = _create_rfp(client, ctx, title="No job yet", line_source="narrative", scope_of_work="Price only.")
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    client.post(f"/public/rfp/{token}", data={"vendor_label": "V", "lump_sum_amount": "100"})
    quote_id = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"]).get_json()["item"]["quotes"][0]["id"]
    with client.application.app_context():
        from app.models import Rfp

        rfp = db.session.get(Rfp, uuid.UUID(item["id"]))
        assert rfp is not None
        rfp.project_id = None
        rfp.lead_estimate_id = None
        db.session.commit()
    awarded = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": quote_id},
        headers=ctx["hdr"],
    )
    assert awarded.status_code == 400
    assert "project" in (awarded.get_json().get("error") or "").lower()


def test_award_requires_vendor_company(client, no_dev_admin):
    ctx = _staff(client)
    item = _create_rfp(client, ctx, title="Unlinked quote", line_source="narrative", scope_of_work="Price only.")
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    client.post(f"/public/rfp/{token}", data={"vendor_label": "V", "lump_sum_amount": "50"})
    quote_id = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"]).get_json()["item"]["quotes"][0]["id"]
    with client.application.app_context():
        q = db.session.get(RfpVendorQuote, uuid.UUID(quote_id))
        assert q is not None
        q.vendor_company_id = None
        db.session.commit()
    awarded = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": quote_id},
        headers=ctx["hdr"],
    )
    assert awarded.status_code == 400
    assert "vendor" in (awarded.get_json().get("error") or "").lower()


def test_award_rejects_different_quote_when_po_exists(client, no_dev_admin):
    ctx = _staff(client)
    other = _staff(client)
    item = _create_rfp(client, ctx, title="Two bidders", line_source="narrative", scope_of_work="Price only.")
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={
            "bidders": [
                {"company_id": ctx["vid"], "email": ctx["email"]},
                {"company_id": other["vid"], "email": other["email"]},
            ]
        },
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    quotes = sent.get_json()["item"]["quotes"]
    assert len(quotes) == 2
    for q in quotes:
        posted = client.post(
            f"/public/rfp/{q['invite_token']}",
            data={"vendor_label": q.get("vendor_label") or "V", "lump_sum_amount": "80"},
        )
        assert posted.status_code == 200
    got = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"]).get_json()["item"]["quotes"]
    first, second = got[0]["id"], got[1]["id"]
    awarded = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": first},
        headers=ctx["hdr"],
    )
    assert awarded.status_code == 200, awarded.get_data(as_text=True)
    blocked = client.post(
        f"/api/v1/rfps/{item['id']}/award",
        json={"quote_id": second},
        headers=ctx["hdr"],
    )
    assert blocked.status_code == 400
    assert "different" in (blocked.get_json().get("error") or "").lower()


def test_drawing_token_link_and_freeze(client, no_dev_admin):
    ctx = _staff(client)
    with client.application.app_context():
        d = Drawing(
            project_id=uuid.UUID(ctx["pid"]),
            document_type="drawing",
            title="A101 Floor plan",
            sheet_number="A101",
            sheet_title="Floor plan",
            discipline="Architectural",
            original_filename="A101.pdf",
            mime_type="application/pdf",
        )
        db.session.add(d)
        db.session.commit()
        did = str(d.id)
    item = _create_rfp(client, ctx, title="With sheets", scope_of_work="Price per plans.")
    put = client.put(
        f"/api/v1/rfps/{item['id']}/drawings",
        json={"drawings": [{"drawing_id": did, "delivery": "link"}]},
        headers=ctx["hdr"],
    )
    assert put.status_code == 200, put.get_data(as_text=True)
    assert put.get_json()["item"]["drawings"]
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    page = client.get(f"/public/rfp/{token}")
    assert page.status_code == 200
    assert b"Drawings" in page.data
    files = client.get(f"/public/rfp/{token}/files")
    assert files.status_code == 200
    assert b"A101" in files.data
    preview = client.get(f"/api/v1/rfps/{item['id']}/email-preview", headers=ctx["hdr"])
    assert preview.get_json()["from"] == "quotes@gousis.com"
    text = preview.get_json()["text"] or ""
    assert "A101" in text
    assert "View drawings" in text
    assert "backblaze" not in text.lower()
    html = preview.get_json()["html"] or ""
    assert "cid:" not in html.lower()
    assert preview.get_json()["attach_bytes"] == 0


def test_remaining_scopes_create(client, no_dev_admin):
    ctx = _staff(client)
    with client.application.app_context():
        est = Estimate(project_id=uuid.UUID(ctx["pid"]), name="Remain", status="draft")
        db.session.add(est)
        db.session.flush()
        tl = TakeoffLineItem(
            project_id=uuid.UUID(ctx["pid"]),
            estimate_id=est.id,
            description="Paint",
            quantity=Decimal("1"),
            unit="LS",
            unit_cost=Decimal("100"),
            extended_total=Decimal("100"),
        )
        db.session.add(tl)
        db.session.commit()
        eid = str(est.id)
    created = client.post(
        "/api/v1/rfps",
        json={
            "project_id": ctx["pid"],
            "estimate_id": eid,
            "remaining_scopes": True,
            "title": "Remaining",
            "due_at": _due(),
        },
        headers=ctx["hdr"],
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    item = created.get_json()["item"]
    assert item["line_source"] == "takeoff"
    assert len(item["line_items"]) == 1
    assert item["line_items"][0]["description"] == "Paint"


_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n"


def test_portal_accepts_pdf_quote_without_prices(client, no_dev_admin):
    ctx = _staff(client)
    item = _create_rfp(
        client,
        ctx,
        title="PDF only package",
        line_source="narrative",
        scope_of_work="Price corridor finishes from the attached quote.",
    )
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    page = client.get(f"/public/rfp/{token}")
    assert page.status_code == 200
    assert b'name="quote_pdf"' in page.data
    assert b"Drop your quote PDF here" in page.data
    posted = client.post(
        f"/public/rfp/{token}",
        data={
            "vendor_label": "Quote Vendor",
            "quote_pdf": (BytesIO(_PDF), "vendor-quote.pdf"),
        },
    )
    assert posted.status_code == 200, posted.get_data(as_text=True)
    got = client.get(f"/api/v1/rfps/{item['id']}", headers=ctx["hdr"])
    quote = got.get_json()["item"]["quotes"][0]
    assert quote["received_at"]
    assert quote["lump_sum_amount"] is None
    assert quote["attachments"]
    assert quote["attachments"][0]["name"] == "vendor-quote.pdf"
    file_url = quote["attachments"][0]["file_url"]
    assert file_url
    dl = client.get(file_url, headers=ctx["hdr"])
    assert dl.status_code == 200, dl.get_data(as_text=True)[:400]
    assert dl.data.startswith(b"%PDF")


def test_staff_quote_pdf_upload_and_reject_non_pdf(client, no_dev_admin):
    ctx = _staff(client)
    item = _create_rfp(client, ctx, title="Staff PDF", scope_of_work="Need a vendor PDF.")
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    qid = sent.get_json()["item"]["quotes"][0]["id"]
    bad = client.post(
        f"/api/v1/rfps/{item['id']}/quotes/{qid}/attachments",
        data={"file": (BytesIO(b"not a pdf"), "notes.txt")},
        headers=ctx["hdr"],
    )
    assert bad.status_code == 400
    ok = client.post(
        f"/api/v1/rfps/{item['id']}/quotes/{qid}/attachments",
        data={"file": (BytesIO(_PDF), "quote.pdf")},
        headers=ctx["hdr"],
    )
    assert ok.status_code == 201, ok.get_data(as_text=True)
    row = ok.get_json()["item"]
    assert row["received_at"]
    assert row["attachments"]
    via_vendor = client.post(
        f"/api/v1/rfps/{item['id']}/quote-pdf",
        data={"company_id": ctx["vid"], "file": (BytesIO(_PDF), "second.pdf")},
        headers=ctx["hdr"],
    )
    assert via_vendor.status_code == 201, via_vendor.get_data(as_text=True)
    assert len(via_vendor.get_json()["item"]["attachments"]) >= 2


_PDF_B = b"%PDF-1.4\n1 0 obj\n<</Length 4>>\nstream\nREPL\nendstream\nendobj\n%%EOF\n"


def test_files_page_download_freeze_and_expired_403(client, no_dev_admin):
    from app.models.rfp import Rfp, RfpDrawing
    from app.services.object_storage import UploadCategory, save_upload

    ctx = _staff(client)
    with client.application.app_context():
        d = Drawing(
            project_id=uuid.UUID(ctx["pid"]),
            document_type="drawing",
            title="A201 Plans",
            sheet_number="A201",
            sheet_title="Plans",
            discipline="Architectural",
            original_filename="A201.pdf",
            mime_type="application/pdf",
            file_size_bytes=len(_PDF),
        )
        db.session.add(d)
        db.session.flush()
        save_upload(UploadCategory.DRAWINGS, f"{d.id}.pdf", BytesIO(_PDF))
        db.session.commit()
        did = str(d.id)
    item = _create_rfp(client, ctx, title="Snap sheets", scope_of_work="Price per plans.")
    put = client.put(
        f"/api/v1/rfps/{item['id']}/drawings",
        json={"drawings": [{"drawing_id": did}]},
        headers=ctx["hdr"],
    )
    assert put.status_code == 200, put.get_data(as_text=True)
    sent = client.post(
        f"/api/v1/rfps/{item['id']}/send",
        json={"bidders": [{"company_id": ctx["vid"], "email": ctx["email"]}]},
        headers=ctx["hdr"],
    )
    assert sent.status_code == 200, sent.get_data(as_text=True)
    token = sent.get_json()["item"]["quotes"][0]["invite_token"]
    files = client.get(f"/public/rfp/{token}/files")
    assert files.status_code == 200
    assert b"A201" in files.data
    assert b"Submit quote" in files.data
    with client.application.app_context():
        row = db.session.scalar(select(RfpDrawing).where(RfpDrawing.rfp_id == uuid.UUID(item["id"])))
        assert row is not None
        assert row.b2_key
        assert "/snap/" in row.b2_key
        snap_key = row.b2_key
        drawing_row_id = str(row.id)
        save_upload(UploadCategory.DRAWINGS, f"{did}.pdf", BytesIO(_PDF_B))
        live = db.session.get(Drawing, uuid.UUID(did))
        live.original_filename = "A201-rev2.pdf"
        db.session.commit()
    dl = client.get(f"/public/rfp/{token}/files/{drawing_row_id}/download")
    assert dl.status_code == 200, dl.get_data(as_text=True)[:400]
    assert dl.data.startswith(b"%PDF")
    assert b"REPL" not in dl.data
    with client.application.app_context():
        row = db.session.get(RfpDrawing, uuid.UUID(drawing_row_id))
        assert row.b2_key == snap_key
    zip_post = client.post(f"/public/rfp/{token}/files/zip")
    assert zip_post.status_code in (200, 202, 302)
    zip_get = client.get(f"/public/rfp/{token}/files/zip", follow_redirects=True)
    assert zip_get.status_code == 200
    assert zip_get.data[:2] == b"PK" or zip_get.mimetype == "application/zip"
    with client.application.app_context():
        rfp = db.session.get(Rfp, uuid.UUID(item["id"]))
        rfp.due_at = datetime.now(timezone.utc) - timedelta(days=1)
        db.session.commit()
    closed = client.get(f"/public/rfp/{token}/files")
    assert closed.status_code == 403
    assert b"A201" not in closed.data
    assert client.get(f"/public/rfp/{token}/files/{drawing_row_id}/download").status_code == 403
    assert client.get(f"/public/rfp/{token}").status_code == 403

