"""Register existing B2 job-path drawings onto Project rows (no upload)."""
from __future__ import annotations

import uuid

from app.extensions import db
from app.models import Drawing, Estimate, LeadEstimate, Project
from app.services.b2_project_link import parse_job_drawing_key, register_b2_job_files


def test_parse_job_drawing_key_reads_sheet_path():
    parsed = parse_job_drawing_key(
        "prod/usis-cm/drawings/25270/Architectural/BCK-1/A1-001_BCK-1.pdf",
        "prod/usis-cm",
    )
    assert parsed == {
        "job": "25270",
        "discipline": "Architectural",
        "drawing_set": "BCK-1",
        "filename": "A1-001_BCK-1.pdf",
        "object_name": "25270/Architectural/BCK-1/A1-001_BCK-1.pdf",
    }


def test_parse_job_drawing_key_skips_uuid_legacy():
    assert (
        parse_job_drawing_key(
            "prod/usis-cm/drawings/000c3064-bef4-40bb-b5f5-12ed6f6f86ac.pdf",
            "prod/usis-cm",
        )
        is None
    )


def test_register_b2_job_files_creates_rows_and_is_idempotent(flask_app):
    number = "24" + uuid.uuid4().hex[:3]
    objects = [
        {
            "key": f"prod/usis-cm/drawings/{number}/Architectural/Permit-Set/A1-001_Permit-Set.pdf",
            "size": 1234,
        },
        {
            "key": f"prod/usis-cm/drawings/{uuid.uuid4()}.pdf",
            "size": 99,
        },
    ]
    with flask_app.app_context():
        flask_app.config["B2_PREFIX"] = "prod/usis-cm"
        p = Project(name="Link-" + number, number=number, status="active")
        db.session.add(p)
        db.session.commit()
        pid = p.id

        first = register_b2_job_files(objects=objects)
        db.session.commit()
        assert first["created"] == 1
        assert first["skipped_no_job"] == 1
        assert first["jobs"][number]["created"] == 1

        row = db.session.query(Drawing).filter_by(project_id=pid).one()
        assert row.sheet_number == "A1-001"
        assert row.discipline == "Architectural"
        assert row.drawing_set == "Permit-Set"
        assert (row.tags or {}).get("storage_object") == (
            f"{number}/Architectural/Permit-Set/A1-001_Permit-Set.pdf"
        )
        assert row.file_url == f"/api/v1/drawings/{row.id}/file"
        assert row.file_size_bytes == 1234

        second = register_b2_job_files(objects=objects)
        db.session.commit()
        assert second["created"] == 0
        assert second["already_linked"] == 1
        assert db.session.query(Drawing).filter_by(project_id=pid).count() == 1


def test_register_b2_job_files_lists_on_project_and_lead(client, flask_app):
    number = "25" + uuid.uuid4().hex[:3]
    objects = [
        {
            "key": f"prod/usis-cm/drawings/{number}/Architectural/BCK-1/A1-001_BCK-1.pdf",
            "size": 2000,
        },
        {
            "key": f"prod/usis-cm/drawings/{number}/Architectural/BCK-1/A1-002_BCK-1.pdf",
            "size": 2100,
        },
    ]
    with flask_app.app_context():
        flask_app.config["B2_PREFIX"] = "prod/usis-cm"
        p = Project(name="List-" + number, number=number, status="active")
        db.session.add(p)
        db.session.flush()
        lead = LeadEstimate(
            external_id="b2-link-" + uuid.uuid4().hex[:10],
            name="Linked lead " + number,
            number=number,
            submission_state="UNDECIDED",
        )
        db.session.add(lead)
        db.session.flush()
        est = Estimate(lead_estimate_id=lead.id, name="Est " + number)
        db.session.add(est)
        db.session.commit()
        pid = str(p.id)
        lid = str(lead.id)
        eid = str(est.id)

        payload = register_b2_job_files(objects=objects)
        db.session.commit()
        assert payload["created"] == 2
        assert payload["leads_attached"] >= 1

    listed = client.get(f"/api/v1/projects/{pid}/drawings?limit=2000")
    assert listed.status_code == 200, listed.get_data(as_text=True)
    body = listed.get_json()
    assert body["total"] >= 1
    sheets = {s.get("sheet_number") for s in body["items"]}
    assert "A1-001" in sheets
    assert "A1-002" in sheets

    lead_json = client.get(f"/api/v1/lead-estimates/{lid}").get_json()["item"]
    assert lead_json["drawing_project_id"] == pid
    assert lead_json["project_id"] == pid

    with flask_app.app_context():
        est_row = db.session.get(Estimate, uuid.UUID(eid))
        assert est_row is not None
        assert str(est_row.project_id) == pid
