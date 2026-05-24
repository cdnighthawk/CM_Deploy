"""HR policy acknowledgment helpers (employee handbook, not hire-wizard forms)."""
from __future__ import annotations

HIRE_WIZARD_POLICY_VERSIONS = frozenset(
    {
        "hire-federal-i9-attestation-v1",
        "hire-federal-w4-attestation-v1",
    }
)

DEFAULT_EMPLOYEE_HANDBOOK_VERSION = "handbook-2025-01"
