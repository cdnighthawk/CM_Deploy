"""Spec section PDF upload + streaming (specs book)."""
from __future__ import annotations

import io
import uuid

from app.extensions import db
from app.models import Project, SpecSection


def _minimal_pdf_bytes() -> bytes:
    return b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


def test_spec_section_upload_and_get_file(client):
    with client.application.app_context():
        p = Project(name="SpecF-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        sec = SpecSection(project_id=p.id, code="03 30 00", title="Cast-in-place concrete", is_active=True)
        db.session.add(sec)
        db.session.flush()
        sid = str(sec.id)
        db.session.commit()

    data = {"file": (io.BytesIO(_minimal_pdf_bytes()), "section.pdf")}
    r = client.post(
        f"/api/v1/projects/{pid}/rfi-lookups/spec_sections/{sid}/file",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["entity"] == "spec_sections"
    assert body["item"]["pdf_url"] == f"/api/v1/spec-sections/{sid}/file"

    r2 = client.get(f"/api/v1/spec-sections/{sid}/file")
    assert r2.status_code == 200
    assert r2.mimetype == "application/pdf"
    assert b"%PDF" in r2.data


def test_spec_section_upload_wrong_project(client):
    with client.application.app_context():
        p1 = Project(name="P1-" + uuid.uuid4().hex[:6])
        p2 = Project(name="P2-" + uuid.uuid4().hex[:6])
        db.session.add_all([p1, p2])
        db.session.flush()
        pid1 = str(p1.id)
        pid2 = str(p2.id)
        sec = SpecSection(project_id=p1.id, code="01 00 00", title="General", is_active=True)
        db.session.add(sec)
        db.session.flush()
        sid = str(sec.id)
        db.session.commit()

    data = {"file": (io.BytesIO(_minimal_pdf_bytes()), "a.pdf")}
    r = client.post(
        f"/api/v1/projects/{pid2}/rfi-lookups/spec_sections/{sid}/file",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 404
