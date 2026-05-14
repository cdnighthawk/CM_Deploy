"""Commitment tables register with SQLAlchemy (Sage CM–aligned procurement slice)."""


def test_commitment_tables_in_metadata(flask_app):
    from app.extensions import db

    names = db.metadata.tables.keys()
    assert "commitments" in names
    assert "commitment_line_items" in names
    assert "commitment_bill_allocations" in names
