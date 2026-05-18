"""Role module permissions (company-wide nav / API access)."""
from .access import (
    ModuleAccessError,
    capabilities_for_user,
    effective_permissions,
    effective_permissions_for_user,
    has_module_access,
    http_method_min_level,
    require_module,
    require_module_for_request,
    validate_permissions_payload,
)
from .modules import MODULE_CATALOG, MODULE_CODES, ALL_LEVELS, catalog_public

__all__ = [
    "ALL_LEVELS",
    "MODULE_CATALOG",
    "MODULE_CODES",
    "ModuleAccessError",
    "capabilities_for_user",
    "catalog_public",
    "effective_permissions",
    "effective_permissions_for_user",
    "has_module_access",
    "http_method_min_level",
    "require_module",
    "require_module_for_request",
    "validate_permissions_payload",
]
