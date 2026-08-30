from app.services.ingest_classify import (
    classify_ingest_file,
    guess_document_type,
    should_skip_path,
)


def test_classify_sheet_pdf_as_drawing():
    assert classify_ingest_file("A101_FLOOR-PLAN.pdf")["kind"] == "drawing"
    assert classify_ingest_file("24060/Architectural/Permit/A1-001_BCK-1.pdf")["kind"] == "drawing"


def test_classify_spec_and_photo_as_document():
    spec = classify_ingest_file("24060/Specs/Addendum 2.pdf")
    assert spec["kind"] == "document"
    assert spec["document_type"] == "specification"
    photo = classify_ingest_file("field/photos/wall.jpg")
    assert photo["kind"] == "document"
    assert photo["document_type"] == "photo"


def test_classify_kind_override():
    forced = classify_ingest_file("random.pdf", kind="drawing")
    assert forced["kind"] == "drawing"
    as_doc = classify_ingest_file("A101_FLOOR-PLAN.pdf", kind="document")
    assert as_doc["kind"] == "document"


def test_guess_document_types():
    assert guess_document_type("RFI-012 Response.pdf") == "rfi"
    assert guess_document_type("submittals/package.pdf") == "submittal"
    assert guess_document_type("safety/IIPP.pdf") == "safety_doc"


def test_should_skip_junk():
    assert should_skip_path(".DS_Store")
    assert should_skip_path("__MACOSX/file.pdf")
    assert should_skip_path("foo/.hidden/a.pdf")
    assert not should_skip_path("Architectural/A101.pdf")
