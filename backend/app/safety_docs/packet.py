"""Load Markdown templates and render company programs + project packets."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .context import build_context
from .markdown_html import markdown_to_html, wrap_print_html
from .paths import templates_root
from .render import render_template

COMPANY_DOCS: tuple[tuple[str, str, str], ...] = (
    ("iipp", "IIPP", "company/IIPP.md"),
    ("wvpp", "WVPP", "company/WVPP.md"),
    ("heat", "Heat Illness Prevention", "company/HEAT_ILLNESS_PREVENTION.md"),
    ("hazcom", "Hazard Communication", "company/HAZCOM.md"),
    ("code-of-safe-practices", "Code of Safe Practices", "company/CODE_OF_SAFE_PRACTICES.md"),
)

PACKET_DOCS: tuple[tuple[str, str, str], ...] = (
    ("site-card", "Site Safety Card", "project/SITE_CARD.md"),
    ("orientation", "Orientation acknowledgment", "project/ORIENTATION.md"),
    ("sssp", "Project Safety Plan (SSSP)", "project/SSSP.md"),
    ("daily-ptp", "Daily PTP", "forms/DAILY_PTP.md"),
    ("inspection", "Inspection checklist", "forms/INSPECTION.md"),
    ("toolbox", "Toolbox roster", "forms/TOOLBOX.md"),
    ("incident", "Incident packet", "forms/INCIDENT.md"),
    ("chemical-inventory", "Chemical inventory", "forms/CHEMICAL_INVENTORY.md"),
)


def _read_template(rel: str, root: Path | None = None) -> str:
    path = (root or templates_root()) / rel
    return path.read_text(encoding="utf-8")


def render_named_docs(
    catalog: tuple[tuple[str, str, str], ...],
    company: Mapping[str, Any],
    project: Mapping[str, Any],
    *,
    version: str | int,
    root: Path | None = None,
) -> dict[str, dict[str, str]]:
    ctx = build_context(company, project, version=version)
    out: dict[str, dict[str, str]] = {}
    for slug, title, rel in catalog:
        ctx["doc"]["title"] = f"{title} — {ctx['project']['name']}"
        md = render_template(_read_template(rel, root), ctx)
        out[slug] = {
            "slug": slug,
            "title": title,
            "markdown": md,
            "html": markdown_to_html(md),
        }
    return out


def render_company_docs(
    company: Mapping[str, Any],
    *,
    version: str | int = 1,
    root: Path | None = None,
) -> dict[str, dict[str, str]]:
    return render_named_docs(COMPANY_DOCS, company, {}, version=version, root=root)


def render_packet_docs(
    company: Mapping[str, Any],
    project: Mapping[str, Any],
    *,
    version: str | int,
    root: Path | None = None,
) -> dict[str, dict[str, str]]:
    return render_named_docs(PACKET_DOCS, company, project, version=version, root=root)


def combine_packet_html(docs: Mapping[str, Mapping[str, str]], *, draft: bool, title: str) -> str:
    parts = []
    for slug, _title, _rel in PACKET_DOCS:
        doc = docs.get(slug) or {}
        body = doc.get("html") or ""
        heading = doc.get("title") or slug
        parts.append(f'<section class="packet-section" id="doc-{slug}"><h1>{heading}</h1>{body}</section>')
    return wrap_print_html(title, "\n".join(parts), draft=draft)


def combine_company_html(doc: Mapping[str, str], *, title: str, draft: bool = False) -> str:
    return wrap_print_html(title, doc.get("html") or "", draft=draft)
