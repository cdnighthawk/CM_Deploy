"""Detect pytest / API-test users that should not live in production."""
from __future__ import annotations

import os
import re
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import or_, select

from ..extensions import db
from ..models import User

if TYPE_CHECKING:
    pass

ALLOWLIST_EMAILS = frozenset({"charles@gousis.com"})

PROTECTED_DOMAIN_SUFFIXES = (
    "@godocon.com",
    "@gousis.com",
    "@usis.local",
)

TEST_LOCAL_PREFIXES = (
    "adm_",
    "adm2_",
    "att_",
    "badnext_",
    "bic_owner_",
    "bic_other_",
    "cmp_",
    "d_",
    "doc_u_",
    "em_",
    "hire_",
    "hradm_",
    "hrms_",
    "login_",
    "lo_",
    "mgr_",
    "mobile_",
    "ms_ok_",
    "newu_",
    "next_",
    "out_",
    "pay_u_",
    "pbi_u_",
    "playbook_tester_",
    "priv_",
    "proc_rfp_",
    "proc_u_",
    "prof_",
    "sched_u_",
    "sov_u_",
    "std_",
    "sub_",
    "u_",
)

_TEST_PREFIX_RE = re.compile(
    r"^(" + "|".join(re.escape(p) for p in TEST_LOCAL_PREFIXES) + r")",
    re.IGNORECASE,
)

HR_DEMO_EMAILS = frozenset(
    {
        "hr.demo.employee@usis.local",
        "charles.dossett@usis.local",
    }
)
HR_DEMO_IDS = frozenset(
    {
        uuid.UUID("a1700000-0000-4000-8000-000000000001"),
        uuid.UUID("b1700000-0000-4000-8000-000000000001"),
    }
)


def _bootstrap_admin_email() -> str | None:
    raw = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    return raw or None


def is_test_artifact_email(email: str | None) -> bool:
    """True only when email clearly matches pytest/API test patterns."""
    if not email or not email.strip():
        return False
    e = email.strip().lower()
    if e in ALLOWLIST_EMAILS:
        return False
    bootstrap = _bootstrap_admin_email()
    if bootstrap and e == bootstrap:
        return False
    for suffix in PROTECTED_DOMAIN_SUFFIXES:
        if e.endswith(suffix):
            return False
    if e.endswith("@t.com") or e.endswith("@example.com"):
        return True
    local = e.split("@", 1)[0]
    return bool(_TEST_PREFIX_RE.match(local))


def list_test_artifact_users() -> list[User]:
    rows = db.session.scalars(select(User).order_by(User.email)).all()
    return [u for u in rows if is_test_artifact_email(u.email)]


def is_hr_demo_user(user: User) -> bool:
    email = (user.email or "").strip().lower()
    if email in HR_DEMO_EMAILS:
        return True
    return user.id in HR_DEMO_IDS


def list_hr_demo_users() -> list[User]:
    q = select(User).where(
        or_(
            User.email.in_(sorted(HR_DEMO_EMAILS)),
            User.id.in_(sorted(HR_DEMO_IDS)),
        )
    )
    return list(db.session.scalars(q.order_by(User.email)).all())
