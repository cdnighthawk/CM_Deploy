"""Expand @@include for Time pages into gulp/dist without gulp-clean."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "W3CRM-v3.0-13_September_2025" / "gulp" / "src"
DIST = ROOT / "W3CRM-v3.0-13_September_2025" / "gulp" / "dist"

INCLUDE_RE = re.compile(
    r"""@@include\(\s*["']([^"']+)["']\s*(?:,\s*(\{.*?\}))?\s*\)""",
    re.DOTALL,
)
IF_RE = re.compile(
    r"@@if\s*\((!)?\s*context\.(\w+)\)\s*\{(.*?)\}",
    re.DOTALL,
)
VAR_RE = re.compile(r"@@(\w+)")


def _parse_ctx(raw: str | None) -> dict:
    if not raw:
        return {}
    cleaned = re.sub(r",\s*}", "}", raw.strip())
    cleaned = cleaned.replace("\t", " ")
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def expand(path: Path, ctx: dict) -> str:
    text = path.read_text(encoding="utf-8-sig")

    def replace_include(match: re.Match) -> str:
        rel = match.group(1)
        inner_ctx = dict(ctx)
        inner_ctx.update(_parse_ctx(match.group(2)))
        target = (path.parent / rel).resolve()
        if not target.exists():
            raise FileNotFoundError(f"include missing: {target} from {path}")
        return expand(target, inner_ctx)

    text = INCLUDE_RE.sub(replace_include, text)

    def replace_if(match: re.Match) -> str:
        negated = bool(match.group(1))
        key = match.group(2)
        body = match.group(3)
        present = bool(ctx.get(key))
        keep = (not present) if negated else present
        return body if keep else ""

    text = IF_RE.sub(replace_if, text)

    def replace_var(match: re.Match) -> str:
        key = match.group(1)
        if key in ("include", "if"):
            return match.group(0)
        val = ctx.get(key)
        return str(val) if val is not None else match.group(0)

    return VAR_RE.sub(replace_var, text)


def main() -> None:
    names = [
        "usis-time-live.html",
        "usis-time-me.html",
        "usis-time-cards.html",
        "usis-time-events.html",
        "usis-time-exceptions.html",
        "usis-time-payroll.html",
        "usis-time-map.html",
        "usis-time-settings.html",
    ]
    DIST.mkdir(parents=True, exist_ok=True)
    for name in names:
        src = SRC / name
        out = DIST / name
        html = expand(src, {})
        out.write_text(html, encoding="utf-8", newline="\n")
        print(f"wrote {out} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
