from app.services.ingest import folder_to_project_number, parse_ingest_metadata, project_matches_query


def test_folder_to_project_number_proj_year_seq():
    assert folder_to_project_number("PROJ-2024-0142") == "240142"
    assert folder_to_project_number("proj_2024_142") == "240142"


def test_folder_to_project_number_digits_passthrough():
    assert folder_to_project_number("240142") == "240142"


def test_parse_ingest_metadata_json_string():
    meta = parse_ingest_metadata('{"source":"autodesk_desktop_connector","project_id":"x"}')
    assert meta["source"] == "autodesk_desktop_connector"
    assert parse_ingest_metadata("not-json") == {}
    assert parse_ingest_metadata(None) == {}


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
