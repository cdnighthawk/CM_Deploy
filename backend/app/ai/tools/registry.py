"""Tool definitions (JSON schema) and handler registry."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ...api._perms import CurrentUser

ToolHandler = Callable[[dict[str, Any], CurrentUser], dict[str, Any]]


@dataclass(frozen=True)
class ToolDef:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    """Module code(s) for read access; write tools check write level in handler."""
    modules: tuple[str, ...]


def _obj(props: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": props,
        "required": required or [],
        "additionalProperties": False,
    }


def _tool_schema(defn: ToolDef) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": defn.name,
            "description": defn.description,
            "parameters": defn.parameters,
        },
    }


_REGISTRY: list[ToolDef] = []


def register(defn: ToolDef) -> ToolDef:
    _REGISTRY.append(defn)
    return defn


def all_tools() -> list[ToolDef]:
    return list(_REGISTRY)


def tool_schemas_for_grok() -> list[dict[str, Any]]:
    return [_tool_schema(t) for t in _REGISTRY]


def get_tool(name: str) -> ToolDef | None:
    for t in _REGISTRY:
        if t.name == name:
            return t
    return None


def tool_names() -> list[str]:
    return [t.name for t in _REGISTRY]
