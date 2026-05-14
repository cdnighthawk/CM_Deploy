"""RFI API: create, patch to Open, configurable fields, attachment upload, contractor autofill."""
from __future__ import annotations

import io
import uuid
from datetime import date, timedelta

import pytest

from app.extensions import db
from app.models import Company, Contact, Project, RfiConfigurableField, User


def _minimal_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_rfi_create_open_responsible_autofill(client):
    email = "sub_" + uuid.uuid4().hex[:8] + "@example.com"
    with client.application.app_context():
        comp = Company(name="SubCo-" + uuid.uuid4().hex[:6], company_type="subcontractor")
        db.session.add(comp)
        db.session.flush()
        u_sub = User(email=email, first_name="Sam", last_name="Sub", is_active=True)
        u_mgr = User(email="mgr_" + uuid.uuid4().hex[:8] + "@example.com", first_name="M", last_name="R", is_active=True)
        db.session.add_all([u_sub, u_mgr])
        db.session.flush()
        db.session.add(
            Contact(
                company_id=comp.id,
                first_name="Sam",
                last_name="Sub",
                email=email,
            )
        )
        p = Project(name="RFI-P-" + uuid.uuid4().hex[:6])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        uid_sub = str(u_sub.id)
        uid_mgr = str(u_mgr.id)
        comp_id = str(comp.id)
        db.session.commit()

    due = (date.today() + timedelta(days=7)).isoformat()
    body = {
        "status": "open",
        "subject": "Clarify ceiling height",
        "question": "Is 9'-6\" clear per sheet A701?",
        "due_at": due,
        "rfi_manager_user_id": uid_mgr,
        "received_from_user_id": uid_sub,
        "assignees": [{"user_id": uid_sub, "is_required": True}],
    }
    r = client.post(f"/api/v1/projects/{pid}/rfis", json=body)
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["status"] == "open"
    assert item.get("responsible_contractor") and item["responsible_contractor"]["id"] == comp_id


def test_rfi_configurable_required_blocks_open(client):
    with client.application.app_context():
        u = User(email="u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="A", last_name="B", is_active=True)
        p = Project(name="P2-" + uuid.uuid4().hex[:6])
        db.session.add_all([u, p])
        db.session.flush()
        pid = str(p.id)
        db.session.add(
            RfiConfigurableField(project_id=p.id, field_key="location", requirement="required")
        )
        db.session.commit()
        uid = str(u.id)

    due = (date.today() + timedelta(days=3)).isoformat()
    r = client.post(
        f"/api/v1/projects/{pid}/rfis",
        json={
            "status": "open",
            "subject": "S",
            "question": "Q?",
            "due_at": due,
            "rfi_manager_user_id": uid,
            "assignees": [{"user_id": uid}],
        },
    )
    assert r.status_code == 400
    assert "location" in (r.get_json() or {}).get("error", "").lower()


def test_rfi_draft_then_patch_open(client):
    with client.application.app_context():
        u = User(email="d_" + uuid.uuid4().hex[:8] + "@t.com", first_name="D", last_name="E", is_active=True)
        p = Project(name="P3-" + uuid.uuid4().hex[:6])
        db.session.add_all([u, p])
        db.session.flush()
        pid = str(p.id)
        db.session.commit()
        uid = str(u.id)

    due = (date.today() + timedelta(days=2)).isoformat()
    r1 = client.post(
        f"/api/v1/projects/{pid}/rfis",
        json={
            "status": "draft",
            "subject": "Draft subj",
            "question": "Draft Q",
            "due_at": due,
            "rfi_manager_user_id": uid,
            "assignees": [{"user_id": uid}],
        },
    )
    assert r1.status_code == 201
    rid = r1.get_json()["item"]["id"]
    assert r1.get_json()["item"]["status"] == "draft"

    r2 = client.patch(
        f"/api/v1/rfis/{rid}",
        json={"status": "open"},
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()["item"]["status"] == "open"


def test_rfi_attachment_upload_and_download(client):
    with client.application.app_context():
        u = User(email="att_" + uuid.uuid4().hex[:8] + "@t.com", first_name="A", last_name="T", is_active=True)
        p = Project(name="P4-" + uuid.uuid4().hex[:6])
        db.session.add_all([u, p])
        db.session.flush()
        pid = str(p.id)
        db.session.commit()
        uid = str(u.id)

    due = (date.today() + timedelta(days=1)).isoformat()
    r1 = client.post(
        f"/api/v1/projects/{pid}/rfis",
        json={
            "status": "draft",
            "subject": "Att",
            "question": "Q",
            "due_at": due,
            "rfi_manager_user_id": uid,
            "assignees": [{"user_id": uid}],
        },
    )
    rid = r1.get_json()["item"]["id"]
    data = {"file": (io.BytesIO(_minimal_pdf_bytes()), "spec.pdf")}
    r2 = client.post(f"/api/v1/rfis/{rid}/attachments/upload", data=data, content_type="multipart/form-data")
    assert r2.status_code == 201, r2.get_data(as_text=True)
    doc_id = r2.get_json()["item"]["id"]
    r3 = client.get(f"/api/v1/rfi-attachments/{doc_id}/file")
    assert r3.status_code == 200
    assert b"%PDF" in r3.data
