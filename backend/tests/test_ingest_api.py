"""Bearer ingest routes used by the Autodesk Desktop Connector agent."""
from __future__ import annotations

import hashlib
import io
import json
import uuid

from pypdf import PdfWriter

from app.extensions import db
from app.models import Document, Drawing, Estimate, LeadEstimate, Project


def _pdf_bytes() -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _auth(flask_app, key: str = "cmk_test_ingest_key"):
    flask_app.config["CM_API_KEY"] = key
    flask_app.config["CM_INGEST_API_KEY"] = None
    return {
        "Authorization": f"Bearer {key}",
        "User-Agent": "CM-Autodesk-Ingestion-Agent/1.1",
    }


def test_ingest_projects_route_exists_without_key(client, flask_app):
    flask_app.config["CM_API_KEY"] = None
    flask_app.config["CM_INGEST_API_KEY"] = None
    r = client.get("/api/projects")
    assert r.status_code == 503
    assert r.is_json
    assert r.get_json()["error"]


def test_ingest_projects_requires_bearer(client, flask_app):
    flask_app.config["CM_API_KEY"] = "cmk_test_ingest_key"
    r = client.get("/api/projects")
    assert r.status_code == 401
    assert r.is_json
    assert "error" in r.get_json()


def test_ingest_projects_rejects_wrong_key(client, flask_app):
    headers = _auth(flask_app)
    r = client.get("/api/projects", headers={**headers, "Authorization": "Bearer wrong-key-value-xx"})
    assert r.status_code == 401


def test_ingest_projects_returns_json_list(client, flask_app):
    headers = _auth(flask_app)
    with flask_app.app_context():
        p = Project(name="Ingest-" + uuid.uuid4().hex[:8], number="240142")
        db.session.add(p)
        db.session.commit()
        pid = str(p.id)

    r = client.get("/api/projects", headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert isinstance(body, dict)
    assert isinstance(body.get("projects"), list)
    match = next((row for row in body["projects"] if row.get("project_id") == pid), None)
    assert match is not None
    assert match["project_number"] == "240142"
    assert match["kind"] == "job"
    assert match["archived"] is False

    r2 = client.get("/api/projects?q=PROJ-2024-0142", headers=headers)
    assert r2.status_code == 200
    found = next((row for row in r2.get_json()["projects"] if row["project_id"] == pid), None)
    assert found is not None


def test_ingest_projects_omits_archived_lead_estimates(client, flask_app):
    headers = _auth(flask_app)
    suffix = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        keep = LeadEstimate(
            external_id=f"ingest-keep-{suffix}",
            name=f"Active Ingest Lead {suffix}",
            is_archived=False,
            is_parent=True,
            submission_state="UNDECIDED",
        )
        archived = LeadEstimate(
            external_id=f"ingest-arch-{suffix}",
            name=f"Archived Ingest Lead {suffix}",
            is_archived=True,
            workflow_bucket="ARCHIVED",
            submission_state="UNDECIDED",
        )
        child = LeadEstimate(
            external_id=f"ingest-child-{suffix}",
            name=f"Active Ingest Lead {suffix}",
            is_archived=False,
            is_parent=False,
            external_parent_id="parent-1",
            workflow_bucket="CHILD",
            submission_state="UNDECIDED",
        )
        db.session.add_all([keep, archived, child])
        db.session.commit()
        keep_id = str(keep.id)
        archived_id = str(archived.id)
        child_id = str(child.id)

    r = client.get("/api/projects", headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    ids = {row["project_id"] for row in r.get_json()["projects"]}
    assert keep_id in ids
    assert archived_id not in ids
    assert child_id not in ids
    keep_row = next(row for row in r.get_json()["projects"] if row["project_id"] == keep_id)
    assert keep_row["archived"] is False


def test_ingest_document_and_drawing_upload(client, flask_app):
    headers = _auth(flask_app)
    pdf = _pdf_bytes()
    digest = hashlib.sha256(pdf).hexdigest()
    with flask_app.app_context():
        p = Project(name="IngestUp-" + uuid.uuid4().hex[:8], number="259999")
        db.session.add(p)
        db.session.commit()
        pid = str(p.id)

    spec = b"%PDF-1.4 spec sample"
    spec_hash = hashlib.sha256(spec).hexdigest()
    doc_r = client.post(
        "/api/documents",
        headers=headers,
        data={
            "file": (io.BytesIO(spec), "addendum.pdf"),
            "metadata": json.dumps(
                {
                    "source": "autodesk_desktop_connector",
                    "content_hash": spec_hash,
                    "project_id": pid,
                    "document_type": "specification",
                }
            ),
        },
        content_type="multipart/form-data",
    )
    assert doc_r.status_code == 201, doc_r.get_data(as_text=True)
    doc_body = doc_r.get_json()
    assert doc_body["document"]["content_hash"] == spec_hash
    assert doc_body["project"]["project_id"] == pid
    assert doc_body["matchedBy"] == "project_id"

    dup = client.post(
        "/api/documents",
        headers=headers,
        data={
            "file": (io.BytesIO(spec), "addendum.pdf"),
            "metadata": json.dumps(
                {
                    "source": "autodesk_desktop_connector",
                    "content_hash": spec_hash,
                    "project_id": pid,
                }
            ),
        },
        content_type="multipart/form-data",
    )
    assert dup.status_code == 200
    assert dup.get_json()["duplicate"] is True

    draw_r = client.post(
        "/api/drawings",
        headers=headers,
        data={
            "file": (io.BytesIO(pdf), "A101.pdf"),
            "metadata": json.dumps(
                {
                    "source": "autodesk_desktop_connector",
                    "content_hash": digest,
                    "project_id": pid,
                    "sheet_number": "A101",
                }
            ),
        },
        content_type="multipart/form-data",
    )
    assert draw_r.status_code == 201, draw_r.get_data(as_text=True)
    draw_body = draw_r.get_json()
    assert draw_body["drawing"]["drawing_id"]
    assert draw_body["drawing"]["content_hash"] == digest

    with flask_app.app_context():
        assert db.session.get(Document, uuid.UUID(doc_body["document"]["id"])) is not None
        drawing = db.session.get(Drawing, uuid.UUID(draw_body["drawing"]["id"]))
        assert drawing is not None
        assert drawing.sheet_number == "A101"
        assert drawing.project_id == uuid.UUID(pid)

    file_r = client.get(f"/api/v1/documents/{doc_body['document']['id']}/file")
    assert file_r.status_code == 200
    assert file_r.data == spec

    with flask_app.app_context():
        saved = db.session.get(Document, uuid.UUID(doc_body["document"]["id"]))
        assert saved is not None
        key = (saved.tags or {}).get("storage_object")
        assert key == f"259999/specification/addendum.pdf"


def test_ingest_replace_drawing_file(client, flask_app):
    headers = _auth(flask_app)
    first = _pdf_bytes()
    replacement = _pdf_bytes() + b"\n%replaced\n"
    with flask_app.app_context():
        p = Project(name="IngestRep-" + uuid.uuid4().hex[:8], number="259998")
        db.session.add(p)
        db.session.commit()
        pid = str(p.id)

    created = client.post(
        "/api/drawings",
        headers=headers,
        data={
            "file": (io.BytesIO(first), "A200.pdf"),
            "metadata": json.dumps(
                {
                    "source": "autodesk_desktop_connector",
                    "project_id": pid,
                    "sheet_number": "A200",
                }
            ),
        },
        content_type="multipart/form-data",
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    did = created.get_json()["drawing"]["drawing_id"]

    missing = client.post(
        f"/api/drawings/{did}/file",
        headers=headers,
        data={"file": (io.BytesIO(b""), "empty.pdf")},
        content_type="multipart/form-data",
    )
    assert missing.status_code == 400

    replaced = client.post(
        f"/api/drawings/{did}/file",
        headers=headers,
        data={"file": (io.BytesIO(replacement), "A200.pdf")},
        content_type="multipart/form-data",
    )
    assert replaced.status_code == 200, replaced.get_data(as_text=True)
    body = replaced.get_json()
    assert body["replaced"] is True
    assert body["drawing"]["drawing_id"] == did

    file_r = client.get(f"/api/v1/drawings/{did}/file")
    assert file_r.status_code == 200
    assert file_r.data == replacement


def test_ingest_unassigned_upload_when_project_unknown(client, flask_app):
    headers = _auth(flask_app)
    payload = b"unassigned-spec"
    digest = hashlib.sha256(payload).hexdigest()
    r = client.post(
        "/api/documents",
        headers=headers,
        data={
            "file": (io.BytesIO(payload), "notes.txt"),
            "metadata": json.dumps(
                {
                    "source": "autodesk_desktop_connector",
                    "content_hash": digest,
                    "folder_name": "NO-SUCH-FOLDER",
                }
            ),
        },
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["project"] is None
    assert body["document"]["project_id"] is None


def test_ingest_drawing_for_lead_creates_workspace_and_links_estimate(client, flask_app):
    headers = _auth(flask_app)
    pdf = _pdf_bytes()
    suffix = uuid.uuid4().hex[:8]
    with flask_app.app_context():
        lead = LeadEstimate(
            external_id=f"ingest-ws-{suffix}",
            name=f"Unlinked Lead {suffix}",
            number=f"LN{suffix[:6]}",
            is_archived=False,
            is_parent=True,
            submission_state="UNDECIDED",
        )
        db.session.add(lead)
        db.session.flush()
        est = Estimate(name="Original", lead_estimate_id=lead.id, project_id=None)
        db.session.add(est)
        db.session.commit()
        lead_id = str(lead.id)
        estimate_id = str(est.id)

    draw_r = client.post(
        "/api/drawings",
        headers=headers,
        data={
            "file": (io.BytesIO(pdf), "A301.pdf"),
            "metadata": json.dumps(
                {
                    "source": "autodesk_desktop_connector",
                    "project_id": lead_id,
                    "sheet_number": "A301",
                    "folder_name": f"Unlinked Lead {suffix}",
                }
            ),
        },
        content_type="multipart/form-data",
    )
    assert draw_r.status_code == 201, draw_r.get_data(as_text=True)
    body = draw_r.get_json()
    job_id = body["drawing"]["project_id"]
    assert job_id
    assert job_id != lead_id
    assert body["project"]["kind"] == "job"
    assert body["project"]["job_id"] == job_id
    assert body["project"]["lead_estimate_id"] == lead_id

    with flask_app.app_context():
        drawing = db.session.get(Drawing, uuid.UUID(body["drawing"]["drawing_id"]))
        lead = db.session.get(LeadEstimate, uuid.UUID(lead_id))
        est = db.session.get(Estimate, uuid.UUID(estimate_id))
        assert drawing is not None
        assert drawing.project_id == uuid.UUID(job_id)
        assert lead is not None and lead.project_id == uuid.UUID(job_id)
        assert est is not None and est.project_id == uuid.UUID(job_id)
        assert drawing.tags.get("lead_estimate_id") == lead_id

    listed = client.get(f"/api/v1/projects/{job_id}/drawings")
    assert listed.status_code == 200, listed.get_data(as_text=True)
    sheets = listed.get_json()["items"]
    assert any(s.get("sheet_number") == "A301" for s in sheets)


def test_relink_unassigned_drawing_uses_folder_and_lead_tag(client, flask_app):
    headers = _auth(flask_app)
    pdf = _pdf_bytes()
    suffix = uuid.uuid4().hex[:8]
    folder = f"Relink Job {suffix}"
    with flask_app.app_context():
        lead = LeadEstimate(
            external_id=f"ingest-relink-{suffix}",
            name=folder,
            number=f"RL{suffix[:6]}",
            is_archived=False,
            is_parent=True,
            submission_state="UNDECIDED",
        )
        db.session.add(lead)
        db.session.flush()
        orphan = Drawing(
            title="Orphan sheet",
            sheet_number="A401",
            original_filename="A401.pdf",
            mime_type="application/pdf",
            project_id=None,
            tags={
                "source": "autodesk_desktop_connector",
                "source_id": f"{folder}/Architectural/A401.pdf",
                "lead_estimate_id": str(lead.id),
            },
        )
        db.session.add(orphan)
        db.session.commit()
        did = str(orphan.id)
        lead_id = str(lead.id)

    r = client.post("/api/v1/drawings/relink", headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    payload = r.get_json()
    assert payload["linked"] >= 1
    assert any(item["id"] == did for item in payload["items"])

    with flask_app.app_context():
        drawing = db.session.get(Drawing, uuid.UUID(did))
        lead = db.session.get(LeadEstimate, uuid.UUID(lead_id))
        assert drawing is not None and drawing.project_id is not None
        assert lead is not None and lead.project_id == drawing.project_id
