"""Static catalog of printable / embeddable reports for Reports UI.

Authorization is enforced on each render route; this module only describes URLs and parameters.
"""
from __future__ import annotations

from typing import Any

from ._quote_report_columns import column_options_for_catalog

# Categories match major sections on reports.html (Estimating, Sales, etc.).
_REPORTS: list[dict[str, Any]] = [
    {
        "id": "estimate_summary",
        "title": "Lead estimate — takeoff summary (print)",
        "category": "Estimating",
        "description": "All takeoff lines for a lead with section grouping; open then use Print to PDF or paper.",
        "kind": "html_route",
        "url_template": "/api/v1/lead-estimates/{lead_identifier}/render/estimate-summary",
        "required_params": [
            {
                "name": "lead_identifier",
                "label": "Lead ID",
                "hint": "UUID, external_id, or id from estimate URL (?id=…)",
            },
        ],
    },
    {
        "id": "quote_report",
        "title": "Quote report (print)",
        "category": "Estimating",
        "description": "Client quote with your company letterhead, project/opportunity header, and takeoff lines. "
        "Use query parameter columns=id1,id2 (see column_options) to show internal fields such as job cost codes or notes.",
        "kind": "html_route",
        "url_template": "/api/v1/lead-estimates/{lead_identifier}/render/quote-report",
        "required_params": [
            {
                "name": "lead_identifier",
                "label": "Lead ID",
                "hint": "UUID, external_id, or id from estimate URL (?id=…)",
            },
        ],
        "optional_params": [
            {
                "name": "line_limit",
                "label": "Line limit (optional)",
                "hint": "Max takeoff rows (default 500, cap 5000)",
                "query": True,
            },
        ],
    },
    {
        "id": "door_schedule_print",
        "title": "Door schedule (print)",
        "category": "Estimating",
        "description": "Door openings, hardware set, and exploded takeoff lines per opening.",
        "kind": "html_route",
        "url_template": "/api/v1/lead-estimates/{lead_identifier}/render/door-schedule-html",
        "required_params": [
            {
                "name": "lead_identifier",
                "label": "Lead ID",
                "hint": "UUID, external_id, or id from door-schedule URL",
            },
        ],
    },
    {
        "id": "purchase_order_html",
        "title": "Purchase order (print)",
        "category": "Procurement",
        "description": "Vendor PO from a project commitment (purchase_order kind only).",
        "kind": "html_route",
        "url_template": "/api/v1/projects/{project_id}/commitments/{commitment_id}/render/purchase-order",
        "required_params": [
            {"name": "project_id", "label": "Project UUID"},
            {"name": "commitment_id", "label": "Commitment UUID"},
        ],
    },
    {
        "id": "client_proposal_html",
        "title": "Client proposal (print)",
        "category": "Sales",
        "description": "Project metadata and optional scope lines from a commitment.",
        "kind": "html_route",
        "url_template": "/api/v1/projects/{project_id}/render/client-proposal",
        "required_params": [{"name": "project_id", "label": "Project UUID"}],
        "optional_params": [
            {
                "name": "scope_commitment_id",
                "label": "Scope commitment UUID (optional)",
                "query": True,
            },
        ],
    },
    {
        "id": "powerbi_dashboard",
        "title": "Power BI (embedded)",
        "category": "Analytics",
        "description": "When POWERBI_* is configured, use the Power BI section on this page below.",
        "kind": "external",
        "url_template": None,
        "required_params": [],
    },
]


def reports_catalog_public() -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for row in _REPORTS:
        item = dict(row)
        if item.get("id") == "quote_report":
            item["column_options"] = column_options_for_catalog()
        items.append(item)
    return {"items": items, "entity": "reports_catalog"}
