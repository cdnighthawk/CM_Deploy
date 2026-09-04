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


def test_drawing_upload_labels_from_filename(client):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    with client.application.app_context():
        p = Project(name="DrawLbl-" + uuid.uuid4().hex[:8], number="N" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data={
            "file": (io.BytesIO(payload), "A1-001_ENTRY-PLAN_Rev-02.pdf"),
            "split_pages": "false",
            "drawing_set": "Permit-Set",
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    item = r.get_json()["item"]
    assert item["sheet_number"] == "A1-001"
    assert item.get("discipline") == "Architectural"
    assert item.get("drawing_set") == "Permit-Set"
    assert item.get("label_status") == "ok"


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


def test_drawing_list_file_url_does_not_probe_storage(client, monkeypatch):
    """Listing must not HEAD B2 for old vs new keys."""
    from app.services import drawing_upload as du

    calls = {"n": 0}

    def boom(*_args, **_kwargs):
        calls["n"] += 1
        raise AssertionError("listing must not probe storage")

    monkeypatch.setattr(du, "stored_exists", boom)
    monkeypatch.setattr(du, "resolve_drawing_object_name", boom)

    with client.application.app_context():
        p = Project(name="DrawList-" + uuid.uuid4().hex[:8], number="N" + uuid.uuid4().hex[:6])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data={"file": (io.BytesIO(payload), "A1.pdf"), "sheet_number": "A1"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    listed = client.get(f"/api/v1/projects/{pid}/drawings")
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert items
    assert items[0]["current_revision"]["file_url"].endswith("/file")
    assert calls["n"] == 0


def test_drawing_file_serves_legacy_uuid_key(client):
    """Old ``{uuid}.pdf`` objects still open after the human-readable rename."""
    from app.services.object_storage import UploadCategory, local_path, save_upload

    with client.application.app_context():
        p = Project(name="DrawLegacy-" + uuid.uuid4().hex[:8], number="L" + uuid.uuid4().hex[:6])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data={
            "file": (io.BytesIO(payload), "A2.pdf"),
            "sheet_number": "A2",
            "discipline": "Architectural",
            "drawing_set": "Permit Set",
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["item"]["id"]

    with client.application.app_context():
        d = db.session.get(Drawing, uuid.UUID(did))
        assert d is not None
        human = (d.tags or {}).get("storage_object")
        assert human
        old = f"{d.id}.pdf"
        save_upload(UploadCategory.DRAWINGS, old, io.BytesIO(payload))
        human_path = local_path(UploadCategory.DRAWINGS, human)
        if human_path.is_file():
            human_path.unlink()
        d.tags = {**(d.tags or {}), "storage_object": "missing/new/path.pdf"}
        db.session.commit()

    file_r = client.get(f"/api/v1/drawings/{did}/file")
    assert file_r.status_code == 200
    assert b"%PDF" in file_r.data


def test_drawing_upload_uses_human_readable_storage_name(client):
    from app.services.object_storage import UploadCategory, stored_exists

    with client.application.app_context():
        pnum = "N" + uuid.uuid4().hex[:8]
        p = Project(name="DrawName-" + uuid.uuid4().hex[:8], number=pnum)
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    data = {
        "file": (io.BytesIO(payload), "A7.31_SITE_Rev-00_Permit-Set.pdf"),
        "sheet_number": "A7.31",
        "discipline": "Architectural",
        "drawing_set": "Permit Set",
    }
    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["item"]["id"]

    with client.application.app_context():
        d = db.session.get(Drawing, uuid.UUID(did))
        assert d is not None
        key = (d.tags or {}).get("storage_object")
        assert key == f"{pnum}/Architectural/Permit-Set/A7.31_SITE_Rev-00_Permit-Set.pdf"
        assert stored_exists(UploadCategory.DRAWINGS, key)

    file_r = client.get(f"/api/v1/drawings/{did}/file")
    assert file_r.status_code == 200
    assert b"%PDF" in file_r.data


def test_drawing_patch_sheet_number_and_title(client):
    with client.application.app_context():
        p = Project(name="DrawPatch-" + uuid.uuid4().hex[:8])
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
            "sheet_title": "Old name",
            "revision": rev,
        }
        r = client.post(
            f"/api/v1/projects/{pid}/drawings",
            data=data,
            content_type="multipart/form-data",
        )
        assert r.status_code == 201, r.get_data(as_text=True)
        ids.append(r.get_json()["item"]["id"])

    r_empty = client.patch(f"/api/v1/drawings/{ids[0]}", json={})
    assert r_empty.status_code == 400

    r_rev = client.patch(
        f"/api/v1/drawings/{ids[0]}",
        json={"sheet_title": "Revision name only", "scope": "revision"},
    )
    assert r_rev.status_code == 200, r_rev.get_data(as_text=True)
    body_rev = r_rev.get_json()
    assert body_rev["scope"] == "revision"
    assert body_rev["item"]["sheet_title"] == "Revision name only"
    assert len(body_rev["items"]) == 1

    with client.application.app_context():
        first = db.session.get(Drawing, uuid.UUID(ids[0]))
        second = db.session.get(Drawing, uuid.UUID(ids[1]))
        assert first is not None and second is not None
        assert first.sheet_title == "Revision name only"
        assert first.title == "Revision name only"
        assert second.sheet_title == "Old name"

    r_series = client.patch(
        f"/api/v1/drawings/{ids[1]}",
        json={"sheet_number": "A-102", "sheet_title": "Level 2 plan"},
    )
    assert r_series.status_code == 200, r_series.get_data(as_text=True)
    body = r_series.get_json()
    assert body["scope"] == "series"
    assert body["item"]["sheet_number"] == "A-102"
    assert body["item"]["sheet_title"] == "Level 2 plan"
    assert {item["id"] for item in body["items"]} == set(ids)
    assert all(item["sheet_number"] == "A-102" for item in body["items"])
    assert all(item["sheet_title"] == "Level 2 plan" for item in body["items"])

    listed = client.get(f"/api/v1/projects/{pid}/drawings")
    assert listed.status_code == 200
    sheets = listed.get_json()["items"]
    assert len(sheets) == 1
    assert sheets[0]["sheet_number"] == "A-102"
    assert sheets[0]["sheet_title"] == "Level 2 plan"


def test_pin_sheet_to_set_uses_matching_revision():
    from app.api.v1 import _pin_sheet_to_set

    sheet = {
        "drawing_set": "BCK-4",
        "sheet_title": "Plan BCK-4",
        "current_revision": {
            "id": "new",
            "drawing_set": "BCK-4",
            "revision": "4",
            "sheet_title": "Plan BCK-4",
        },
        "revisions": [
            {
                "id": "new",
                "drawing_set": "BCK-4",
                "revision": "4",
                "sheet_title": "Plan BCK-4",
            },
            {
                "id": "old",
                "drawing_set": "BCK-1",
                "revision": "1",
                "sheet_title": "Plan BCK-1",
            },
        ],
    }
    pinned = _pin_sheet_to_set(sheet, "BCK-1")
    assert pinned is not None
    assert pinned["drawing_set"] == "BCK-1"
    assert pinned["sheet_title"] == "Plan BCK-1"
    assert pinned["current_revision"]["id"] == "old"
    assert _pin_sheet_to_set(sheet, "BCK-3") is None


def test_drawing_row_kept_when_storage_fails_and_retry_reuses_it(client):
    from unittest.mock import patch

    from app.services.object_storage import StorageError

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    with client.application.app_context():
        p = Project(name="DrawPend-" + uuid.uuid4().hex[:8], number="P" + uuid.uuid4().hex[:6])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    data = {
        "file": (io.BytesIO(payload), "G0-000.1.pdf"),
        "sheet_number": "G0-000.1",
        "drawing_set": "Bid Set",
        "revision": "0",
        "split_pages": "false",
    }
    with patch(
        "app.services.drawing_upload.save_upload",
        side_effect=StorageError("Backblaze B2 closed the upload connection (SSL EOF).", 503),
    ):
        r = client.post(
            f"/api/v1/projects/{pid}/drawings",
            data=data,
            content_type="multipart/form-data",
        )
    assert r.status_code == 503, r.get_data(as_text=True)
    body = r.get_json()
    assert body["file_pending"] is True
    did = body["item"]["id"]
    assert did

    with client.application.app_context():
        row = db.session.get(Drawing, uuid.UUID(did))
        assert row is not None
        assert (row.tags or {}).get("file_pending") is True
        assert row.file_size_bytes == 0

    retry = {
        "file": (io.BytesIO(payload), "G0-000.1.pdf"),
        "sheet_number": "G0-000.1",
        "drawing_set": "Bid Set",
        "revision": "0",
        "split_pages": "false",
    }
    with patch("app.services.drawing_upload.save_upload", return_value=2048):
        r2 = client.post(
            f"/api/v1/projects/{pid}/drawings",
            data=retry,
            content_type="multipart/form-data",
        )
    assert r2.status_code == 201, r2.get_data(as_text=True)
    assert r2.get_json()["item"]["id"] == did
    with client.application.app_context():
        rows = db.session.query(Drawing).filter_by(project_id=uuid.UUID(pid)).all()
        assert len(rows) == 1
        assert rows[0].file_size_bytes == 2048
        assert not (rows[0].tags or {}).get("file_pending")


def test_drawing_storage_failure_hands_native_b2_not_s3_presign(client):
    """After Render→S3 fails, the desktop must get a native B2 upload URL."""
    from unittest.mock import patch

    from app.services.object_storage import StorageError

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    with client.application.app_context():
        p = Project(name="DrawNative-" + uuid.uuid4().hex[:8], number="P" + uuid.uuid4().hex[:6])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    native = {
        "mode": "b2_native",
        "url": "https://pod-000-1000-00.backblaze.com/b2api/v2/b2_upload_file/...",
        "authorization": "tok",
        "file_name": "drawings/sheet.pdf",
        "sha1_header": "X-Bz-Content-Sha1",
    }
    data = {
        "file": (io.BytesIO(payload), "G0-000.2.pdf"),
        "sheet_number": "G0-000.2",
        "drawing_set": "Bid Set",
        "revision": "0",
        "split_pages": "false",
    }
    with (
        patch(
            "app.services.drawing_upload.save_upload",
            side_effect=StorageError(
                "Backblaze B2 closed the S3-compatible upload connection.",
                503,
            ),
        ),
        patch(
            "app.services.object_storage.native_upload_session",
            return_value=native,
        ) as mock_native,
        patch(
            "app.services.object_storage.presigned_put_url",
            return_value="https://s3.us-west-004.backblazeb2.com/usis-cm/broken",
        ) as mock_presign,
    ):
        r = client.post(
            f"/api/v1/projects/{pid}/drawings",
            data=data,
            content_type="multipart/form-data",
        )
    assert r.status_code == 503, r.get_data(as_text=True)
    body = r.get_json()
    assert body["upload"]["mode"] == "b2_native"
    assert "pod-" in body["upload"]["url"]
    assert body["upload"].get("authorization") == "tok"
    mock_native.assert_called_once()
    mock_presign.assert_not_called()


def test_drawing_storage_failure_does_not_fall_back_to_s3_presign(client):
    """If native B2 session cannot be issued, do not hand the desktop an S3 PUT."""
    from unittest.mock import patch

    from app.services.object_storage import StorageError

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    with client.application.app_context():
        p = Project(name="DrawNoS3-" + uuid.uuid4().hex[:8], number="P" + uuid.uuid4().hex[:6])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    data = {
        "file": (io.BytesIO(payload), "G0-000.3.pdf"),
        "sheet_number": "G0-000.3",
        "drawing_set": "Bid Set",
        "revision": "0",
        "split_pages": "false",
    }
    with (
        patch(
            "app.services.drawing_upload.save_upload",
            side_effect=StorageError("could not save file: ConnectionClosedError", 500),
        ),
        patch("app.services.object_storage.native_upload_session", return_value=None),
        patch(
            "app.services.object_storage.presigned_put_url",
            return_value="https://s3.us-west-004.backblazeb2.com/usis-cm/broken",
        ) as mock_presign,
    ):
        r = client.post(
            f"/api/v1/projects/{pid}/drawings",
            data=data,
            content_type="multipart/form-data",
        )
    assert r.status_code == 500, r.get_data(as_text=True)
    body = r.get_json()
    assert body.get("upload") is None
    mock_presign.assert_not_called()


def test_put_drawing_file_replaces_pdf(client):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    with client.application.app_context():
        p = Project(name="DrawPut-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data={"file": (io.BytesIO(payload), "A1.pdf"), "split_pages": "false"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["item"]["id"]

    r2 = client.put(
        f"/api/v1/drawings/{did}/file",
        data={"file": (io.BytesIO(payload), "A1.pdf")},
        content_type="multipart/form-data",
    )
    assert r2.status_code == 200, r2.get_data(as_text=True)
    assert r2.get_json()["item"]["id"] == did
    file_r = client.get(f"/api/v1/drawings/{did}/file")
    assert file_r.status_code == 200
    assert b"%PDF" in file_r.data


def test_drawing_upload_session_and_ack_file(client):
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    payload = buf.getvalue()

    with client.application.app_context():
        p = Project(name="DrawSess-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(
        f"/api/v1/projects/{pid}/drawings",
        data={"file": (io.BytesIO(payload), "A1.pdf"), "split_pages": "false"},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    did = r.get_json()["item"]["id"]

    native = {
        "mode": "b2_native",
        "url": "https://pod-000.backblaze.com/b2api/v2/b2_upload_file",
        "authorization": "tok",
        "file_name": "drawings/A1.pdf",
        "sha1_header": "X-Bz-Content-Sha1",
    }
    from unittest.mock import patch

    with patch(
        "app.services.object_storage.native_upload_session",
        return_value=native,
    ):
        sess = client.post(f"/api/v1/drawings/{did}/upload-session")
    assert sess.status_code == 200, sess.get_data(as_text=True)
    assert sess.get_json()["upload"]["mode"] == "b2_native"

    ack = client.post(
        f"/api/v1/drawings/{did}/ack-file",
        json={"byte_size": len(payload), "content_hash": "abc"},
    )
    assert ack.status_code == 200, ack.get_data(as_text=True)
    assert ack.get_json()["item"]["file_pending"] is False
    with client.application.app_context():
        row = db.session.get(Drawing, uuid.UUID(did))
        assert row is not None
        assert row.file_size_bytes == len(payload)
        assert not (row.tags or {}).get("file_pending")
