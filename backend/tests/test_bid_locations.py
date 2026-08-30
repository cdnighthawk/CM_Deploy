"""CPU first-pass: bid-by-floor / area / building from notes and titles."""
from __future__ import annotations

from app.api._bid_locations import classify_bid_locations, extract_locations, looks_like_bid_doc


def test_required_from_bid_instructions():
    out = classify_bid_locations(
        [("lead.trade_specific_instructions", "Provide a breakdown by floor on the bid form.")]
    )
    assert out["requirement"] == "required"
    assert out["grain"] == "floor"
    assert out["needsAi"] is True  # named instruction, no named floors yet


def test_required_with_named_floors_is_not_an_ai_exception():
    out = classify_bid_locations(
        [
            ("lead.notes", "Bid by floor."),
            ("drawing.title", "A-101 Level 1 Floor Plan"),
            ("drawing.title", "A-102 Level 2 Floor Plan"),
        ]
    )
    assert out["requirement"] == "required"
    assert out["needsAi"] is False
    labels = {x["label"] for x in out["locations"]}
    assert "Level 1" in labels
    assert "Level 2" in labels


def test_not_found_when_nothing_says_to_break_the_bid():
    out = classify_bid_locations([("drawing.title", "A-101 Floor Plan")])
    assert out["requirement"] == "not_found"
    assert out["needsAi"] is False


def test_unclear_when_many_floors_but_no_instruction():
    out = classify_bid_locations(
        [
            ("drawing.title", "Level 1 Floor Plan"),
            ("drawing.title", "Level 2 Floor Plan"),
            ("drawing.title", "Level 3 Floor Plan"),
        ]
    )
    assert out["requirement"] == "unclear"
    assert out["needsAi"] is True


def test_unclear_when_bid_docs_exist_but_titles_are_silent():
    out = classify_bid_locations(
        [("document", "Invitation to Bid.pdf")],
        bid_doc_count=1,
    )
    assert out["requirement"] == "unclear"
    assert out["needsAi"] is True


def test_building_and_area_extraction():
    locs = extract_locations(
        [
            ("drawing.title", "Building A Level 1 Floor Plan"),
            ("drawing.title", "Area B Finish Plan"),
            ("drawing.title", "Building Section"),
        ]
    )
    labels = {x["label"] for x in locs}
    assert "Building A" in labels
    assert "Area B" in labels
    assert "Building SECTION" not in labels


def test_bid_doc_filename_hints():
    assert looks_like_bid_doc("ITB Addendum 2", "ITB-02.pdf")
    assert looks_like_bid_doc("Instructions to Bidders")
    assert not looks_like_bid_doc("A-101 Floor Plan", "A-101.pdf")


def test_building_grain_from_package_notes():
    out = classify_bid_locations(
        [("bid_scope.notes", "GC wants a separate price per building. Building 1 and Building 2.")]
    )
    assert out["requirement"] == "required"
    assert out["grain"] == "building"
    labels = {x["label"] for x in out["locations"]}
    assert "Building 1" in labels
    assert "Building 2" in labels
