"""Unit tests for purge_test_users matching and production guard."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(_SCRIPTS))

_spec = importlib.util.spec_from_file_location(
    "purge_test_users",
    _SCRIPTS / "purge_test_users.py",
)
purge_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(purge_mod)

_guard_spec = importlib.util.spec_from_file_location(
    "_script_db_guard",
    _SCRIPTS / "_script_db_guard.py",
)
guard_mod = importlib.util.module_from_spec(_guard_spec)
assert _guard_spec.loader is not None
_guard_spec.loader.exec_module(guard_mod)

is_test = purge_mod.is_test_artifact_email


@pytest.mark.parametrize(
    "email",
    [
        "adm_abc123@t.com",
        "playbook_tester_deadbeef@example.com",
        "mobile_0123456789@t.com",
        "jamie.rivera@example.com",
    ],
)
def test_matches_test_artifacts(email: str) -> None:
    assert is_test(email) is True


@pytest.mark.parametrize(
    "email",
    [
        "charles@gousis.com",
        "admin@godocon.com",
        "hr.demo.employee@usis.local",
        "charles.dossett@usis.local",
        "real.person@gousis.com",
    ],
)
def test_protected_emails_not_matched(email: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BOOTSTRAP_ADMIN_EMAIL", raising=False)
    assert is_test(email) is False


def test_bootstrap_admin_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "bootstrap@godocon.com")
    assert is_test("bootstrap@godocon.com") is False


def test_production_guard_blocks_execute_without_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@dpg-abc.oregon-postgres.render.com/usis_cm",
    )
    with pytest.raises(SystemExit) as exc:
        guard_mod.require_safe_execute(
            execute=True,
            production_ack=False,
            script_name="purge_test_users.py",
        )
    assert exc.value.code == 2


def test_production_guard_allows_with_ack(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@dpg-abc.oregon-postgres.render.com/usis_cm",
    )
    guard_mod.require_safe_execute(
        execute=True,
        production_ack=True,
        script_name="purge_test_users.py",
    )


def test_local_host_not_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://usis_app:secret@127.0.0.1:5432/usis_cm",
    )
    assert guard_mod.is_production_database() is False
    guard_mod.require_safe_execute(
        execute=True,
        production_ack=False,
        script_name="purge_test_users.py",
    )
