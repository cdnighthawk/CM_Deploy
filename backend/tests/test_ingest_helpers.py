from types import SimpleNamespace

from app.services.ingest import (
    _folder_hint_from_path,
    folder_to_project_number,
    lead_is_archived,
    parse_ingest_metadata,
    project_matches_query,
    serialize_project,
)


def test_folder_to_project_number_proj_year_seq():
    assert folder_to_project_number("PROJ-2024-0142") == "240142"
    assert folder_to_project_number("proj_2024_142") == "240142"


def test_folder_to_project_number_digits_passthrough():
    assert folder_to_project_number("240142") == "240142"


def test_folder_hint_from_relative_path():
    assert _folder_hint_from_path("Hospital Reno/Architectural/A-101.pdf") == "Hospital Reno"
    assert _folder_hint_from_path("PROJ-2024-0142\\A101.pdf") == "PROJ-2024-0142"
    assert _folder_hint_from_path("") == ""


def test_parse_ingest_metadata_json_string():
    meta = parse_ingest_metadata('{"source":"autodesk_desktop_connector","project_id":"x"}')
    assert meta["source"] == "autodesk_desktop_connector"
    assert parse_ingest_metadata("not-json") == {}
    assert parse_ingest_metadata(None) == {}


def test_lead_is_archived_flag_and_bucket():
    assert lead_is_archived(SimpleNamespace(is_archived=True, workflow_bucket=None, submission_state=None))
    assert lead_is_archived(SimpleNamespace(is_archived=False, workflow_bucket="BC_ARCHIVED", submission_state=None))
    assert lead_is_archived(SimpleNamespace(is_archived=False, workflow_bucket=None, submission_state="DECLINED"))
    assert not lead_is_archived(SimpleNamespace(is_archived=False, workflow_bucket="ACTIVE", submission_state="UNDECIDED"))


def test_serialize_project_includes_archived_false_by_default():
    import uuid

    row = serialize_project(
        project_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        kind="lead",
        name="Rooms To Go",
        project_number=None,
        job_id=None,
        lead_estimate_id=uuid.UUID("11111111-1111-4111-8111-111111111111"),
        archived=False,
    )
    assert row["archived"] is False


def test_project_matches_query_uses_folder_hints():
    project = {
        "id": "abc",
        "project_id": "abc",
        "name": "Main Hospital",
        "project_number": "240142",
        "folder_hints": ["240142", "Main Hospital"],
    }
    assert project_matches_query(project, "PROJ-2024-0142")
    assert project_matches_query(project, "hospital")
    assert not project_matches_query(project, "nope")
