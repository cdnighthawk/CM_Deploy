"""Locate the safety-automation template package on disk."""
from __future__ import annotations

from pathlib import Path

# backend/app/safety_docs/paths.py → repo root is parents[3]
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PACKAGE = _REPO_ROOT / "docs" / "safety-automation"


def package_root() -> Path:
    return _PACKAGE


def templates_root() -> Path:
    return _PACKAGE / "templates"


def seed_company_path() -> Path:
    return _PACKAGE / "data" / "company.seed.json"


def sample_project_path() -> Path:
    return _PACKAGE / "data" / "project.mammoth.sample.json"
