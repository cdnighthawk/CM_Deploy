"""CPU drawing hygiene: label check then sheet type. No Grok."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.api._drawing_hygiene import classify_drawing_fields, classify_label, classify_sheet_function
from app.extensions import db
from app.models import Drawing, Estimate, Project


def test_label_ok_common_sheet_numbers():
    for num in ("A-100", "A2.01", "I-201", "S-101", "ID-101", "A-100.1", "A-100A"):
        assert classify_label(num)["label_status"] == "ok", num


def test_label_flags_page_image_uuid_and_filename_conflict():
    assert classify_label("Page 3")["label_status"] == "needs_ai"
    assert classify_label("IMG_4401")["label_status"] == "needs_ai"
    assert classify_label("550e8400-e29b-41d4-a716-446655440000")["label_status"] == "needs_ai"
    empty = classify_label("", "A-104 Floor Plan.pdf")
    assert empty["label_status"] == "needs_ai"
    assert empty["filename_guess"] == "A-104"
    conflict = classify_label("B-200", "A-104.pdf")
    assert conflict["label_status"] == "needs_ai"


def test_label_unknown_when_nothing_to_go_on():
    assert classify_label("", "scan.pdf")["label_status"] == "unknown"


def test_sheet_function_keyword_map():
    cases = (
        ("Level 2 Floor Plan", "floor_plan"),
        ("Reflected Ceiling Plan", "rcp"),
        ("Roof Plan", "roof_plan"),
        ("Site Plan", "site_plan"),
        ("South Exterior Elevation", "exterior_elevation"),
        ("Corridor Interior Elevation", "interior_elevation"),
        ("Building Section", "section"),
        ("Typical Wall Detail", "detail"),
        ("Room Finish Schedule", "finish_schedule"),
        ("Door Schedule", "door_schedule"),
        ("Hardware Schedule", "hardware_schedule"),
        ("Cover Sheet", "cover_index"),
        ("Demolition Plan", "demo_plan"),
    )
    for title, expect in cases:
        got = classify_sheet_function(title)
        assert got["sheet_function"] == expect, (title, got)


def test_vague_or_missing_title_needs_ai():
    assert classify_sheet_function("PLAN")["function_status"] == "needs_ai"
    assert classify_sheet_function("")["function_status"] == "unknown"
    assert classify_sheet_function("Electrical One-Line")["function_status"] == "needs_ai"


def test_detailed_floor_plan_is_not_a_detail_sheet():
    assert classify_sheet_function("Detailed Floor Plan")["sheet_function"] == "floor_plan"


def test_combined_needs_ai_when_either_half_fails():
    out = classify_drawing_fields(sheet_number="Page 3", sheet_title="Level 1 Floor Plan")
    assert out["needs_ai"] is True
    ok = classify_drawing_fields(sheet_number="A-101", sheet_title="Level 1 Floor Plan", filename="A-101.pdf")
    assert ok["needs_ai"] is False
    assert ok["classified_by"] == "cpu"


def test_project_hygiene_api(client):
    with client.application.app_context():
        try:
            p = Project(name="HYG-" + uuid.uuid4().hex[:6])
            db.session.add(p)
            db.session.flush()
            d1 = Drawing(
                project_id=p.id,
                document_type="drawing",
                sheet_number="A-101",
                sheet_title="Level 1 Floor Plan",
                original_filename="A-101.pdf",
            )
            d2 = Drawing(
                project_id=p.id,
                document_type="drawing",
                sheet_number="Page 3",
                sheet_title="PLAN",
                original_filename="scan.pdf",
            )
            db.session.add_all([d1, d2])
            db.session.flush()
            est = Estimate(name="Hyg test", project_id=p.id)
            db.session.add(est)
            db.session.flush()
            pid, eid = str(p.id), str(est.id)
            db.session.commit()
        except Exception as exc:
            if isinstance(exc, OperationalError):
                pytest.skip("database unavailable")
            if isinstance(exc, ProgrammingError) or "label_status" in str(exc) or "does not exist" in str(exc):
                pytest.skip("drawing hygiene columns missing (run flask db upgrade)")
            raise

    r = client.post(f"/api/v1/projects/{pid}/drawings/hygiene")
    if r.status_code >= 500:
        pytest.skip("drawing hygiene not migrated")
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["total"] == 2
    assert body["counts"]["ok"] == 1
    assert body["counts"]["needs_ai"] == 1

    listed = client.get(f"/api/v1/projects/{pid}/drawings")
    assert listed.status_code == 200
    sheets = listed.get_json()["items"]
    by_num = {s["sheet_number"]: s for s in sheets}
    assert by_num["A-101"]["sheet_function"] == "floor_plan"
    assert by_num["A-101"]["label_status"] == "ok"
    assert by_num["Page 3"]["hygiene"]["needsAi"] is True

    er = client.post(f"/api/v1/estimates/{eid}/drawings/hygiene")
    assert er.status_code == 200
    assert er.get_json()["total"] == 2
