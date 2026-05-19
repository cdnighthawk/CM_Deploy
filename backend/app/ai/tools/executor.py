"""Execute AI tools with RBAC and audit logging."""
from __future__ import annotations

import json
import uuid
from typing import Any

from flask import current_app, g, has_app_context, has_request_context

from ...api._perms import CurrentUser
from ...permissions.access import ModuleAccessError, has_module_access, require_module
from .registry import ToolDef, get_tool


class ToolExecutionError(Exception):
    def __init__(self, message: str, *, status: int = 400):
        super().__init__(message)
        self.message = message
        self.status = status


def _require_tool_read(cu: CurrentUser, tool: ToolDef) -> None:
    if cu.is_dev_admin:
        return
    if not tool.modules:
        return
    for code in tool.modules:
        if has_module_access(cu, code, "read"):
            return
    names = ", ".join(tool.modules)
    raise ToolExecutionError(f"access denied: requires read on one of: {names}", status=403)


def _audit_tool(cu: CurrentUser, tool_name: str, args: dict[str, Any], *, ok: bool, error: str | None = None) -> None:
    if not has_app_context():
        return
    rid = getattr(g, "request_id", None) if has_request_context() else None
    uid = str(cu.id) if cu.id else None
    summary = {k: args.get(k) for k in list(args.keys())[:8]}
    current_app.logger.info(
        "ai_tool name=%s user_id=%s request_id=%s ok=%s error=%s args=%s",
        tool_name,
        uid,
        rid,
        ok,
        error,
        json.dumps(summary, default=str)[:500],
    )


def run_tool(name: str, arguments: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    tool = get_tool(name)
    if tool is None:
        out = {"ok": False, "error": f"unknown tool: {name}"}
        _audit_tool(cu, name, arguments or {}, ok=False, error=out["error"])
        return out

    args = arguments if isinstance(arguments, dict) else {}
    try:
        _require_tool_read(cu, tool)
        result = tool.handler(args, cu)
        if not isinstance(result, dict):
            result = {"ok": True, "data": result}
        if "ok" not in result:
            result = {"ok": True, **result}
        _audit_tool(cu, name, args, ok=bool(result.get("ok", True)))
        return result
    except ModuleAccessError as exc:
        out = {"ok": False, "error": exc.message, "status": exc.status}
        _audit_tool(cu, name, args, ok=False, error=exc.message)
        return out
    except ToolExecutionError as exc:
        out = {"ok": False, "error": exc.message, "status": exc.status}
        _audit_tool(cu, name, args, ok=False, error=exc.message)
        return out
    except Exception as exc:
        current_app.logger.exception("ai_tool %s failed", name)
        out = {"ok": False, "error": str(exc)}
        _audit_tool(cu, name, args, ok=False, error=str(exc))
        return out


def require_module_write(cu: CurrentUser, module_code: str) -> None:
    require_module(cu, module_code, "write")


def parse_uuid(raw: Any, field: str = "id") -> uuid.UUID:
    if raw in (None, ""):
        raise ToolExecutionError(f"{field} is required")
    try:
        return uuid.UUID(str(raw))
    except ValueError as exc:
        raise ToolExecutionError(f"invalid {field}") from exc
