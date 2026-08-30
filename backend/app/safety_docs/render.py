"""Handlebars subset matching docs/safety-automation/engine/generate.mjs."""
from __future__ import annotations

import re
from typing import Any, Mapping

_IF_OPEN = re.compile(r"\{\{#if ([a-zA-Z0-9_.]+)\}\}")
_EACH_CHEM = re.compile(r"\{\{#each chemicals\}\}")
_TOKEN = re.compile(r"\{\{([^}#/]+)\}\}")


def get_path(obj: Any, path: str) -> Any:
    cur = obj
    for key in path.split("."):
        if cur is None:
            return None
        if isinstance(cur, Mapping):
            cur = cur.get(key)
        else:
            cur = getattr(cur, key, None)
    return cur


def _truthy(key: str, value: Any) -> bool:
    if key.startswith("scope.") or key.startswith("climate."):
        return value is True or value == "Yes"
    if value is True or value == "Yes":
        return True
    if isinstance(value, str):
        return bool(value) and value != "—"
    return bool(value)


def _find_close(template: str, start: int, open_re: re.Pattern[str], close_lit: str) -> int | None:
    """Return index of matching close tag, skipping nested opens of the same kind."""
    depth = 1
    i = start
    while i < len(template):
        m = open_re.match(template, i)
        if m:
            depth += 1
            i = m.end()
            continue
        if template.startswith(close_lit, i):
            depth -= 1
            if depth == 0:
                return i
            i += len(close_lit)
            continue
        i += 1
    return None


def _replace_if_blocks(template: str, data: Mapping[str, Any]) -> str:
    out = template
    guard = 0
    while guard < 200:
        guard += 1
        m = _IF_OPEN.search(out)
        if not m:
            break
        close = _find_close(out, m.end(), _IF_OPEN, "{{/if}}")
        if close is None:
            break
        key = m.group(1)
        inner = out[m.end() : close]
        keep = _truthy(key, get_path(data, key))
        out = out[: m.start()] + (inner if keep else "") + out[close + len("{{/if}}") :]
    return out


def _replace_chemicals(template: str, data: Mapping[str, Any]) -> str:
    chemicals = data.get("chemicals") if isinstance(data.get("chemicals"), list) else []
    out = template
    guard = 0
    while guard < 20:
        guard += 1
        m = _EACH_CHEM.search(out)
        if not m:
            break
        close = out.find("{{/each}}", m.end())
        if close < 0:
            break
        body = out[m.end() : close]
        else_idx = body.find("{{else}}")
        if else_idx >= 0:
            row, empty = body[:else_idx], body[else_idx + len("{{else}}") :]
        else:
            row, empty = body, ""
        if not chemicals:
            rendered = empty
        else:
            chunks = []
            for c in chemicals:
                item = c if isinstance(c, Mapping) else {}
                chunk = row
                for field in ("productName", "manufacturer", "useLocation", "sdsUrl"):
                    chunk = chunk.replace("{{" + field + "}}", str(item.get(field) or ""))
                chunks.append(chunk)
            rendered = "".join(chunks)
        out = out[: m.start()] + rendered + out[close + len("{{/each}}") :]
    return out


def _replace_tokens(template: str, data: Mapping[str, Any]) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1).strip()
        v = get_path(data, key)
        if v is None or v == "":
            return "—"
        if isinstance(v, (dict, list)):
            import json

            return json.dumps(v)
        return str(v)

    return _TOKEN.sub(repl, template)


def render_template(template: str, data: Mapping[str, Any]) -> str:
    out = _replace_if_blocks(template, data)
    out = _replace_chemicals(out, data)
    return _replace_tokens(out, data)
