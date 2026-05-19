"""Drawing PDF upload — multi-page split into one sheet per page."""
from __future__ import annotations

import io
import uuid

from pypdf import PdfWriter

from app.extensions import db
from app.models import Drawing, Project


def _two_page_pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_drawing_upload_splits_multi_page_pdf(client):
    with client.application.app_context():
        p = Project(name="Draw-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    data = {
        "file": (io.BytesIO(_two_page_pdf_bytes()), "plan-set.pdf"),
        "split_pages": "true",
    }
    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["entity"] == "drawing_upload"
    assert body["split"] is True
    assert body["count"] == 2
    assert len(body["items"]) == 2
    assert body["items"][0]["sheet_number"] == "Page 1"
    assert body["items"][1]["sheet_number"] == "Page 2"

    with client.application.app_context():
        rows = db.session.query(Drawing).filter_by(project_id=uuid.UUID(pid)).all()
        assert len(rows) == 2

    for item in body["items"]:
        r2 = client.get(f"/api/v1/drawings/{item['id']}/file")
        assert r2.status_code == 200
        assert r2.mimetype == "application/pdf"
        assert b"%PDF" in r2.data


def test_drawing_upload_single_page_no_split_entity(client):
    with client.application.app_context():
        p = Project(name="Draw1-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    data = {"file": (io.BytesIO(payload), "single.pdf")}
    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["entity"] == "drawing"
    assert "item" in body


def test_drawing_delete_revision_and_series(client):
    with client.application.app_context():
        p = Project(name="DrawDel-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    ids: list[str] = []
    for rev in ("A", "B"):
        data = {
            "file": (io.BytesIO(payload), f"sheet-{rev}.pdf"),
            "sheet_number": "A101",
            "revision": rev,
        }
        r = client.post(
            f"/api/v1/projects/{pid}/drawings",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 201, r.get_data(as_text=True)
        ids.append(r.get_json()["item"]["id"])

    with client.application.app_context():
        rows = db.session.query(Drawing).filter_by(project_id=uuid.UUID(pid)).all()
        assert len(rows) == 2
        series_id = rows[0].drawing_series_id
        assert all(r.drawing_series_id == series_id for r in rows)

    r_del = client.post(
        f"/api/v1/drawings/{ids[0]}/delete",
        json={"scope": "revision", "confirm": True},
    )
    assert r_del.status_code == 200, r_del.get_data(as_text=True)
    assert r_del.get_json()["deleted"] == 1

    with client.application.app_context():
        rows = db.session.query(Drawing).filter_by(project_id=uuid.UUID(pid)).all()
        assert len(rows) == 1

    r_file = client.get(f"/api/v1/drawings/{ids[0]}/file")
    assert r_file.status_code == 404

    r_series = client.post(
        f"/api/v1/drawings/{ids[1]}/delete",
        json={"scope": "series", "confirm": True},
    )
    assert r_series.status_code == 200, r_series.get_data(as_text=True)
    assert r_series.get_json()["deleted"] == 1

    with client.application.app_context():
        rows = db.session.query(Drawing).filter_by(project_id=uuid.UUID(pid)).all()
        assert len(rows) == 0
