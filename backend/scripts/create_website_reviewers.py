"""Create the website_reviewer role and three read-only reviewer accounts.

From ``backend/``:

  python scripts/create_website_reviewers.py
  python scripts/create_website_reviewers.py --execute

Optional env overrides for passwords (otherwise unique passwords are generated):

  REVIEWER1_PASSWORD
  REVIEWER2_PASSWORD
  REVIEWER3_PASSWORD
"""
from __future__ import annotations

import argparse
import os
import secrets
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_BACKEND / ".env", override=True)

from sqlalchemy import select  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.auth import Role, RoleModulePermission, User, UserRole  # noqa: E402
from app.models.project import Project  # noqa: E402
from app.models.project_member import ProjectMember  # noqa: E402
from app.permissions.defaults import (  # noqa: E402
    DEFAULTS_BY_ROLE_CODE,
    WEBSITE_REVIEWER_ROLE_CODE,
)

REVIEWER_ACCOUNTS: tuple[tuple[str, str, str, str], ...] = (
    ("reviewer1@usis.local", "Reviewer", "One", "REVIEWER1_PASSWORD"),
    ("reviewer2@usis.local", "Reviewer", "Two", "REVIEWER2_PASSWORD"),
    ("reviewer3@usis.local", "Reviewer", "Three", "REVIEWER3_PASSWORD"),
)


def _password_for(env_key: str) -> str:
    raw = (os.environ.get(env_key) or "").strip()
    if raw:
        if len(raw) < 8:
            raise SystemExit(f"{env_key} must be at least 8 characters.")
        return raw
    return secrets.token_urlsafe(12)


def _ensure_role(code: str, name: str, description: str) -> Role:
    role = db.session.scalar(select(Role).where(Role.code == code))
    if role is None:
        role = Role(code=code, name=name, description=description)
        db.session.add(role)
        db.session.flush()
        print(f"Created role {code}")
    else:
        role.name = name
        role.description = description
        print(f"Updated role {code}")

    wanted = DEFAULTS_BY_ROLE_CODE.get(code) or {}
    existing = {row.module_code: row for row in role.module_permissions}
    for module_code, access_level in wanted.items():
        row = existing.get(module_code)
        if row is None:
            role.module_permissions.append(
                RoleModulePermission(module_code=module_code, access_level=access_level)
            )
        else:
            row.access_level = access_level
    return role


def _assign_all_projects(user: User) -> int:
    project_ids = db.session.scalars(select(Project.id).where(Project.deleted_at.is_(None))).all()
    existing = set(
        db.session.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user.id)).all()
    )
    added = 0
    for project_id in project_ids:
        if project_id in existing:
            continue
        db.session.add(ProjectMember(user_id=user.id, project_id=project_id, member_role="reviewer"))
        added += 1
    return added


def _ensure_user(email: str, first: str, last: str, password: str, roles: list[Role]) -> User:
    user = db.session.scalar(select(User).where(User.email == email))
    action = "Updated"
    if user is None:
        user = User(
            email=email,
            first_name=first,
            last_name=last,
            is_active=True,
            is_superuser=False,
        )
        db.session.add(user)
        db.session.flush()
        action = "Created"
    else:
        user.first_name = first
        user.last_name = last
        user.is_active = True
        user.is_superuser = False

    user.password_hash = generate_password_hash(password)

    for role in roles:
        already = db.session.scalar(
            select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == role.id)
        )
        if already is None:
            db.session.add(UserRole(user_id=user.id, role_id=role.id))

    assigned = _assign_all_projects(user)
    print(f"{action} user {email} ({assigned} project memberships added)")
    return user


def main() -> None:
    parser = argparse.ArgumentParser(description="Create website reviewer role and users")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Write the role and users (default is a dry-run).",
    )
    args = parser.parse_args()

    planned = [(email, first, last, _password_for(env_key)) for email, first, last, env_key in REVIEWER_ACCOUNTS]

    print("Website reviewer accounts:")
    for email, first, last, password in planned:
        print(f"  {email}  ({first} {last})")
        print(f"    password: {password}")

    if not args.execute:
        print("\nDry-run only. Re-run with --execute to write these accounts.")
        return

    app = create_app()
    with app.app_context():
        reviewer_role = _ensure_role(
            WEBSITE_REVIEWER_ROLE_CODE,
            "Website Reviewer",
            "Company-wide read-only access for site review; no user admin",
        )
        # Current production code already treats this legacy code as read-only.
        legacy_read = _ensure_role(
            "read_only",
            "Read only",
            "Legacy read-only role used by current production permission checks",
        )
        for email, first, last, password in planned:
            _ensure_user(email, first, last, password, [reviewer_role, legacy_read])
        db.session.commit()
        print("Website reviewer accounts are ready. Sign in at /page-login.html")


if __name__ == "__main__":
    main()
