"""Unit tests for pytest project detection."""
from __future__ import annotations

from types import SimpleNamespace

from app.projects.test_artifacts import is_test_artifact_project


def _p(name: str, number: str | None = None):
    return SimpleNamespace(name=name, number=number)


def test_detects_pytest_name_patterns():
    assert is_test_artifact_project(_p("Detail-0ef10bcb63", "NUM-0ef10bcb63"))
    assert is_test_artifact_project(_p("Att-19d0d801"))
    assert is_test_artifact_project(_p("PayProj-005782ad"))
    assert is_test_artifact_project(_p("RFI-P-0983ec"))
    assert is_test_artifact_project(_p("P2-ae30cf"))
    assert is_test_artifact_project(_p("Admin ann"))
    assert is_test_artifact_project(_p("BIC test"))


def test_keeps_real_project_names():
    assert not is_test_artifact_project(_p("Capitol Annex", "24125"))
    assert not is_test_artifact_project(
        _p("240583 / Aerospace Building A6 Consolidation Project", "25057")
    )
