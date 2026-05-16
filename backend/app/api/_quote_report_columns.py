"""Column registry for client quote report (print HTML).

Single source for catalog metadata and server-side rendering whitelist.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteColumn:
    id: str
    label: str
    row_key: str
    client_default: bool
    numeric: bool = False


QUOTE_REPORT_COLUMNS: tuple[QuoteColumn, ...] = (
    QuoteColumn("section", "Section", "section", True, False),
    QuoteColumn("description", "Description", "description", True, False),
    QuoteColumn("cost_type", "Type (L/M/E/S/O)", "cost_type", False, False),
    QuoteColumn("line_role", "Line role", "line_role", False, False),
    QuoteColumn("quantity", "Qty", "quantity", True, True),
    QuoteColumn("unit", "Unit", "unit", True, False),
    QuoteColumn("unit_cost", "Unit price", "unit_cost", True, True),
    QuoteColumn("extended", "Extended", "extended_total", True, True),
    QuoteColumn("job_cost_code", "Job cost code", "job_cost_code", False, False),
    QuoteColumn("job_cost_code_description", "Cost code description", "job_cost_code_description", False, False),
    QuoteColumn("material_catalog", "Catalog item", "material_catalog", False, False),
    QuoteColumn("notes", "Notes", "notes", False, False),
)

_COLUMN_BY_ID: dict[str, QuoteColumn] = {c.id: c for c in QUOTE_REPORT_COLUMNS}


def default_column_ids() -> list[str]:
    return [c.id for c in QUOTE_REPORT_COLUMNS if c.client_default]


def resolve_visible_columns(columns_raw: str | None) -> list[QuoteColumn]:
    """Parse ``columns=a,b,c`` query param; unknown ids ignored; empty falls back to defaults."""
    if not columns_raw or not str(columns_raw).strip():
        return [_COLUMN_BY_ID[i] for i in default_column_ids() if i in _COLUMN_BY_ID]
    parts = [p.strip() for p in str(columns_raw).split(",") if p.strip()]
    out: list[QuoteColumn] = []
    for p in parts:
        c = _COLUMN_BY_ID.get(p)
        if c is not None:
            out.append(c)
    if not out:
        return [_COLUMN_BY_ID[i] for i in default_column_ids() if i in _COLUMN_BY_ID]
    return out


def column_options_for_catalog() -> list[dict]:
    return [
        {"id": c.id, "label": c.label, "default": c.client_default}
        for c in QUOTE_REPORT_COLUMNS
    ]
