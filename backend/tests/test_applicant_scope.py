"""Applicant role and public shell scope."""
from __future__ import annotations

from app.permissions.applicant import (
    APPLICANT_PUBLIC_SHELL_PAGES,
    APPLICANT_ROLE_CODE,
    applicant_permissions,
    is_applicant_only_user,
    is_applicant_public_shell_path,
)


def test_applicant_permissions_all_none():
    perms = applicant_permissions()
    assert all(level == "none" for level in perms.values())


def test_applicant_public_shell_paths():
    assert is_applicant_public_shell_path("apply.html")
    assert is_applicant_public_shell_path("apply/application.html")
    assert is_applicant_public_shell_path("apply/i9.html")
    assert is_applicant_public_shell_path("assets/js/usis-hr-hire.js")
    assert not is_applicant_public_shell_path("usis-dashboard-dark.html")


def test_is_applicant_only_user_by_role_codes():
    class _Role:
        def __init__(self, code: str):
            self.code = code

    class _UserRole:
        def __init__(self, code: str):
            self.role = _Role(code)

    class _User:
        is_superuser = False

        def __init__(self, codes: list[str]):
            self.roles = [_UserRole(c) for c in codes]

    assert is_applicant_only_user(_User([APPLICANT_ROLE_CODE]))
    assert not is_applicant_only_user(_User(["project_manager"]))
    assert not is_applicant_only_user(_User(["applicant", "project_manager"]))
    assert not is_applicant_only_user(_User([]))


def test_public_shell_page_list_covers_hire_flow():
    assert "apply.html" in APPLICANT_PUBLIC_SHELL_PAGES
    assert "usis-hr-hire.html" in APPLICANT_PUBLIC_SHELL_PAGES
    assert "page-register.html" in APPLICANT_PUBLIC_SHELL_PAGES
