"""Safety document merge engine (Handlebars templates + company/project JSON)."""
from __future__ import annotations

from .context import build_context, missing_fields
from .markdown_html import wrap_print_html
from .packet import (
    COMPANY_DOCS,
    PACKET_DOCS,
    render_company_docs,
    render_packet_docs,
)
from .paths import templates_root
from .render import render_template

__all__ = [
    "COMPANY_DOCS",
    "PACKET_DOCS",
    "build_context",
    "missing_fields",
    "render_company_docs",
    "render_packet_docs",
    "render_template",
    "templates_root",
    "wrap_print_html",
]
