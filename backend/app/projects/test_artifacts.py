"""Detect pytest / API-test projects that should not live in production."""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import Project

# Exact names created in backend/tests (and a few integration tests).
_TEST_PROJECT_EXACT_NAMES = frozenset(
    {
        "admin ann",
        "bic test",
        "rollup api test project",
        "uniquesearchwidgetxyz",
        "scoped sync",
        "scope test job",
        "job a",
        "job b",
        "assigned",
        "other",
        "x1",
        "x2",
        "px",
        "py",
        "pz",
    }
)

# Prefix + random hex suffix patterns from pytest fixtures.
_TEST_PROJECT_NAME_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^detail-[0-9a-f]{10}$",
        r"^num-[0-9a-f]{10}$",  # name field sometimes empty; number checked separately
        r"^att-[0-9a-f]{8}$",
        r"^docproj-[0-9a-f]{8}$",
        r"^schedproj-[0-9a-f]{8}$",
        r"^payproj-[0-9a-f]{8}$",
        r"^sovproj-[0-9a-f]{8}$",
        r"^specf-[0-9a-f]{8}$",
        r"^proc-[0-9a-f]{8}$",
        r"^procrfp-[0-9a-f]{8}$",
        r"^rfi-p-[0-9a-f]{6}$",
        r"^p[1-5]-[0-9a-f]{6}$",
        r"^t-[0-9a-f]{10}$",
        r"^draw(-|1-|del-)[0-9a-f]{8}$",
    )
)

_TEST_PROJECT_NUMBER_PATTERN = re.compile(r"^num-[0-9a-f]{10}$", re.IGNORECASE)


def is_test_artifact_project(project: Project) -> bool:
    """True when name or number clearly matches pytest/API test fixtures."""
    name = (project.name or "").strip()
    number = (project.number or "").strip()
    if number and _TEST_PROJECT_NUMBER_PATTERN.match(number):
        return True
    if name:
        low = name.lower()
        if low in _TEST_PROJECT_EXACT_NAMES:
            return True
        for pat in _TEST_PROJECT_NAME_PATTERNS:
            if pat.match(name):
                return True
    return False
