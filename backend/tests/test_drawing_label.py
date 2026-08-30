from app.api._drawing_hygiene import classify_label
from app.services.drawing_label import (
    discipline_from_sheet_number,
    is_sheet_number,
    label_drawing,
    parse_filename,
    parse_folder_path,
)


def test_parse_common_sheet_filenames():
    cases = (
        ("A1-001_BCK-1.pdf", "A1-001", "BCK 1"),
        ("G0.1.01_SHEET-INDEX-VOLUME-1_Rev-120.pdf", "G0.1.01", "SHEET INDEX VOLUME 1"),
        ("A10.02.1_FINISH-PLAN-L2-SECTOR-1_Rev-04_Bulletin-15.pdf", "A10.02.1", "FINISH PLAN L2 SECTOR 1"),
        ("A-100 Floor Plan.pdf", "A-100", "Floor Plan"),
        ("P3-G0.1.01_SHEET-INDEX.pdf", "P3-G0.1.01", "SHEET INDEX"),
    )
    for name, sheet, title_part in cases:
        got = parse_filename(name)
        assert got["sheet_number"] == sheet, (name, got)
        assert title_part.lower() in (got["sheet_title"] or "").lower(), (name, got)


def test_revision_from_filename():
    got = parse_filename("A7.31_SITE_Rev-00_Permit-Set.pdf")
    assert got["sheet_number"] == "A7.31"
    assert got["revision"] == "00"


def test_folder_path_job_discipline_set():
    got = parse_folder_path("25270/Architectural/Permit-Set/A1-001_BCK-1.pdf")
    assert got["job"] == "25270"
    assert got["discipline"] == "Architectural"
    assert got["drawing_set"] == "Permit-Set"


def test_label_drawing_fills_discipline_from_sheet_prefix():
    got = label_drawing(filename="A1-001_ENTRY.pdf")
    assert got["sheet_number"] == "A1-001"
    assert got["discipline"] == "Architectural"
    got_g = label_drawing(filename="G0.1.01_INDEX.pdf")
    assert got_g["discipline"] == "General"


def test_hygiene_accepts_real_job_sheet_numbers():
    for num in ("A1-001", "G0.1.01", "A10.02.1", "G0.1.03-A", "P3-G0.1.01"):
        assert is_sheet_number(num), num
        assert classify_label(num)["label_status"] == "ok", num


def test_discipline_from_sheet_number():
    assert discipline_from_sheet_number("S-101") == "Structural"
    assert discipline_from_sheet_number("E2.01") == "Electrical"
    assert discipline_from_sheet_number("P3-G0.1.01") == "General"
