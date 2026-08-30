"""Minimal Markdown → HTML for the safety templates (headers, tables, lists, emphasis)."""
from __future__ import annotations

import html
import re


def _inline(text: str) -> str:
    s = html.escape(text)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def _is_table_sep(line: str) -> bool:
    t = line.strip()
    if not t.startswith("|"):
        return False
    cells = [c.strip() for c in t.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", c or "") for c in cells)


def _table_row(line: str, header: bool = False) -> str:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    tag = "th" if header else "td"
    inner = "".join(f"<{tag}>{_inline(c)}</{tag}>" for c in cells)
    return f"<tr>{inner}</tr>"


def markdown_to_html(md: str) -> str:
    lines = (md or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    para: list[str] = []
    list_tag: str | None = None

    def flush_para() -> None:
        nonlocal para
        if para:
            out.append("<p>" + " ".join(_inline(p) for p in para) + "</p>")
            para = []

    def flush_list() -> None:
        nonlocal list_tag
        if list_tag:
            out.append(f"</{list_tag}>")
            list_tag = None

    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped:
            flush_para()
            flush_list()
            i += 1
            continue
        if stripped.startswith("#"):
            flush_para()
            flush_list()
            hashes = len(stripped) - len(stripped.lstrip("#"))
            level = min(max(hashes, 1), 6)
            out.append(f"<h{level}>{_inline(stripped[hashes:].strip())}</h{level}>")
            i += 1
            continue
        if stripped in ("---", "***", "___"):
            flush_para()
            flush_list()
            out.append("<hr />")
            i += 1
            continue
        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_sep(lines[i + 1]):
            flush_para()
            flush_list()
            header = _table_row(stripped, header=True)
            i += 2
            body: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                body.append(_table_row(lines[i].strip()))
                i += 1
            out.append("<table><thead>" + header + "</thead><tbody>" + "".join(body) + "</tbody></table>")
            continue
        ul = re.match(r"^[-*+]\s+(.+)$", stripped)
        ol = re.match(r"^\d+\.\s+(.+)$", stripped)
        if ul or ol:
            flush_para()
            tag = "ul" if ul else "ol"
            if list_tag != tag:
                flush_list()
                list_tag = tag
                out.append(f"<{tag}>")
            item = (ul or ol).group(1)
            out.append(f"<li>{_inline(item)}</li>")
            i += 1
            continue
        flush_list()
        para.append(stripped)
        i += 1
    flush_para()
    flush_list()
    return "\n".join(out)


def wrap_print_html(title: str, body_html: str, *, draft: bool = False) -> str:
    watermark = ""
    extra_class = ""
    if draft:
        extra_class = " is-draft"
        watermark = '<div class="draft-banner">DRAFT — NOT FOR MOBILIZATION</div>'
    title_esc = html.escape(title or "Safety document")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title_esc}</title>
<style>
body {{ font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; margin: 2rem; color: #1a1a1a; line-height: 1.45; font-size: 11pt; }}
body.is-draft {{ background: repeating-linear-gradient(-45deg, #fff, #fff 40px, #fff8e6 40px, #fff8e6 80px); }}
.draft-banner {{ background: #8a1c1c; color: #fff; font-weight: 700; text-align: center; padding: 0.45rem 0.75rem; margin: -2rem -2rem 1.25rem; letter-spacing: 0.04em; }}
h1 {{ font-size: 1.35rem; margin: 0 0 0.75rem; }}
h2 {{ font-size: 1.1rem; margin: 1.25rem 0 0.5rem; }}
h3 {{ font-size: 1rem; margin: 1rem 0 0.4rem; }}
table {{ width: 100%; border-collapse: collapse; margin: 0.6rem 0 1rem; font-size: 10pt; }}
th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.5rem; text-align: left; vertical-align: top; }}
th {{ background: #f4f6f8; font-weight: 600; }}
hr {{ border: 0; border-top: 1px solid #ddd; margin: 1.25rem 0; }}
.packet-section {{ break-before: page; page-break-before: always; }}
.packet-section:first-child {{ break-before: auto; page-break-before: auto; }}
.no-print {{ margin-bottom: 1rem; }}
@media print {{
  body {{ margin: 0.5in; }}
  .no-print {{ display: none !important; }}
  .draft-banner {{ margin: -0.5in -0.5in 0.75rem; }}
}}
</style>
</head>
<body class="{extra_class.strip()}">
<div class="no-print"><button type="button" onclick="window.print()">Print…</button></div>
{watermark}
{body_html}
</body>
</html>
"""
