"""Quote report column whitelist helpers."""
from __future__ import annotations

from app.api._quote_report_columns import (
    column_options_for_catalog,
    default_column_ids,
    resolve_visible_columns,
)


def test_default_columns_exclude_internal():
    d = default_column_ids()
    assert "description" in d
    assert "notes" not in d
    assert "job_cost_code" not in d


def test_resolve_visible_columns_empty_falls_back_to_defaults():
    visible = resolve_visible_columns("")
    ids = [c.id for c in visible]
    assert ids == default_column_ids()


def test_resolve_visible_columns_whitelist_order():
    visible = resolve_visible_columns("notes,description,quantity")
    assert [c.id for c in visible] == ["notes", "description", "quantity"]


def test_resolve_visible_columns_ignores_unknown():
    visible = resolve_visible_columns("description,bogus,quantity")
    assert [c.id for c in visible] == ["description", "quantity"]


def test_column_options_for_catalog_shape():
    opts = column_options_for_catalog()
    assert isinstance(opts, list)
    assert all("id" in x and "label" in x and "default" in x for x in opts)
