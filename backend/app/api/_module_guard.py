"""HTTP helpers for module-level access checks."""
from __future__ import annotations

from flask import jsonify, request

from ..permissions.access import (
    ModuleAccessError,
    effective_permissions,
    has_module_access,
    http_method_min_level,
    level_rank,
    module_level,
    require_module,
)
from ._module_routes import resolve_modules
from ._perms import CurrentUser, current_user


def _jsonify_err(message: str, status: int):
    return jsonify({"error": message}), status


def effective_level_for_modules(cu: CurrentUser, module_codes: tuple[str, ...]) -> str:
    best = "none"
    for code in module_codes:
        best = module_level(cu, code) if level_rank(module_level(cu, code)) > level_rank(best) else best
    return best


def require_modules_for_request(
    cu: CurrentUser,
    module_codes: tuple[str, ...],
    method: str | None = None,
) -> None:
    m = method or request.method
    min_level = http_method_min_level(m)
    if cu.is_dev_admin:
        return
    if cu.user is None:
        raise ModuleAccessError("authentication required", 401)
    if level_rank(effective_level_for_modules(cu, module_codes)) >= level_rank(min_level):
        return
    names = ", ".join(module_codes)
    raise ModuleAccessError(
        f"access denied: requires {min_level} on one of: {names}",
        403,
    )


def enforce_module_access_for_path(path: str, method: str, cu: CurrentUser | None = None) -> tuple | None:
    """Return Flask response tuple if denied, else None."""
    modules = resolve_modules(path)
    if not modules:
        return None
    cu = cu or current_user()
    try:
        require_modules_for_request(cu, modules, method)
    except ModuleAccessError as exc:
        return _jsonify_err(exc.message, exc.status)
    return None


def check_module(module_code: str, cu: CurrentUser | None = None):
    cu = cu or current_user()
    try:
        require_module(cu, module_code, http_method_min_level(request.method))
    except ModuleAccessError as exc:
        return _jsonify_err(exc.message, exc.status)
    return None
