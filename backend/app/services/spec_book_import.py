"""Read CSI section codes from a spec-book PDF (bookmarks + page text)."""
from __future__ import annotations

import io
import re
from typing import Any

from ..csi_catalog import get_section, title_for_code
from ..csi_spec import CSI_CODE_RE, CSI_LINE_RE, digits_from_csi, format_csi_display

MAX_IMPORT_SECTIONS = 400
_TITLE_CLEAN_RE = re.compile(r"\s+")


def _clean_title(raw: str) -> str:
    text = _TITLE_CLEAN_RE.sub(" ", (raw or "").strip(" \t-—:.|"))
    return text[:300]


def _add(found: dict[str, dict[str, str]], digits: str, title: str = "") -> None:
    if not digits or len(digits) != 6:
        return
    catalog = get_section(digits)
    nice = _clean_title(title)
    if catalog:
        # Prefer the official catalog title unless the PDF title is more specific.
        if not nice or nice.upper() == catalog["title"].upper() or nice == format_csi_display(digits):
            nice = catalog["title"]
        elif len(nice) < 4:
            nice = catalog["title"]
    if digits not in found:
        found[digits] = {
            "digits": digits,
            "code": format_csi_display(digits) or digits,
            "title": nice or title_for_code(digits) or format_csi_display(digits) or digits,
        }
        return
    if nice and (found[digits]["title"] == found[digits]["code"] or len(nice) > len(found[digits]["title"])):
        if title_for_code(digits) and nice.upper() == found[digits]["title"].upper():
            return
        found[digits]["title"] = nice


def _line_digits(match: re.Match[str]) -> str:
    if match.group(1):
        return f"{match.group(1)}{match.group(2)}{match.group(3)}"
    return match.group(4) or ""


def _from_line(text: str, found: dict[str, dict[str, str]]) -> None:
    for match in CSI_LINE_RE.finditer(text or ""):
        _add(found, _line_digits(match), match.group(5) or "")
    for match in CSI_CODE_RE.finditer(text or ""):
        _add(found, _line_digits(match))


def extract_csi_sections_from_pdf(data: bytes) -> list[dict[str, str]]:
    """Return unique CSI sections found in bookmarks and extracted text."""
    found: dict[str, dict[str, str]] = {}
    try:
        import fitz
    except ImportError:
        fitz = None  # type: ignore

    if fitz is not None:
        try:
            doc = fitz.open(stream=data, filetype="pdf")
        except Exception:
            doc = None
        if doc is not None:
            try:
                for _lvl, title, _page in doc.get_toc() or []:
                    _from_line(str(title or ""), found)
                for page in doc:
                    _from_line(page.get_text() or "", found)
                    if len(found) >= MAX_IMPORT_SECTIONS:
                        break
            finally:
                doc.close()

    if not found:
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            for dest in reader.outline or []:
                _walk_pypdf_outline(dest, found)
            for page in reader.pages:
                _from_line(page.extract_text() or "", found)
                if len(found) >= MAX_IMPORT_SECTIONS:
                    break
        except Exception:
            pass

    items = list(found.values())
    items.sort(key=lambda row: row["digits"])
    return items[:MAX_IMPORT_SECTIONS]


def _walk_pypdf_outline(node: Any, found: dict[str, dict[str, str]]) -> None:
    if isinstance(node, list):
        for child in node:
            _walk_pypdf_outline(child, found)
        return
    title = ""
    if isinstance(node, dict):
        title = str(node.get("/Title") or node.get("title") or "")
    else:
        title = str(getattr(node, "title", "") or "")
    if title:
        _from_line(title, found)


def parse_codes_from_text(text: str) -> list[dict[str, str]]:
    """Test helper: extract sections from plain text."""
    found: dict[str, dict[str, str]] = {}
    _from_line(text, found)
    items = list(found.values())
    items.sort(key=lambda row: row["digits"])
    return items


def resolve_manual_section(code: str, title: str = "") -> dict[str, str] | None:
    digits = digits_from_csi(code)
    if not digits:
        return None
    display = format_csi_display(digits) or digits
    catalog_title = title_for_code(digits)
    nice = _clean_title(title)
    return {
        "digits": digits,
        "code": display,
        "title": nice or catalog_title or display,
    }
