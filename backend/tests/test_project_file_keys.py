"""Old UUID keys and new human-readable B2 keys resolve together."""
from __future__ import annotations

import types
import uuid

from app.services.project_file_keys import (
    document_object_candidates,
    document_storage_relpath,
    drawing_object_candidates,
    drawing_storage_relpath,
    preferred_drawing_object_name,
    spec_object_candidates,
    spec_storage_relpath,
)


def _row(**kwargs):
    data = {"id": uuid.uuid4(), "tags": {}, "project_id": uuid.uuid4()}
    data.update(kwargs)
    return types.SimpleNamespace(**data)


def test_drawing_candidates_prefer_tag_then_human_then_uuid():
    did = uuid.uuid4()
    d = _row(
        id=did,
        original_filename="A1.00_SITE_Rev-00_Permit-Set.pdf",
        discipline="Architectural",
        drawing_set="Permit Set",
        tags={"storage_object": "24060/Architectural/Permit-Set/A1.00_SITE_Rev-00_Permit-Set.pdf"},
    )
    names = drawing_object_candidates(d)
    assert names[0] == "24060/Architectural/Permit-Set/A1.00_SITE_Rev-00_Permit-Set.pdf"
    assert f"{did}.pdf" in names
    assert preferred_drawing_object_name(d) == names[0]


def test_drawing_human_path_uses_job_number():
    d = _row(
        original_filename="G0.02_COVER-SHEET.pdf",
        discipline="General",
        drawing_set="Bulletin 01",
    )
    assert drawing_storage_relpath(d, label="24060") == (
        "24060/General/Bulletin-01/G0.02_COVER-SHEET.pdf"
    )


def test_document_candidates_include_legacy_uuid_prefix(monkeypatch):
    monkeypatch.setattr("app.services.project_file_keys.project_label", lambda _pid: "24060")
    did = uuid.uuid4()
    doc = _row(
        id=did,
        document_type="specification",
        original_filename="07 21 00 Insulation.pdf",
        title="Insulation",
        tags={},
    )
    names = document_object_candidates(doc)
    assert document_storage_relpath(doc, label="24060") == "24060/specification/07 21 00 Insulation.pdf"
    assert any(n.startswith(f"{did}_") for n in names)
    assert str(did) in names
    assert f"{did}.pdf" in names


def test_spec_candidates_include_legacy_uuid_pdf(monkeypatch):
    monkeypatch.setattr("app.services.project_file_keys.project_label", lambda _pid: "24060")
    sid = uuid.uuid4()
    row = _row(id=sid, code="07 21 00", title="Insulation", project_id=uuid.uuid4())
    human = spec_storage_relpath(row, original_filename="Insulation.pdf", label="24060")
    assert human == "24060/specifications/07-21-00_Insulation.pdf"
    names = spec_object_candidates(row)
    # spec_object_candidates rebuilds the human path via project_label; UUID fallback is what
    # existing website uploads used.
    assert f"{sid}.pdf" in names
