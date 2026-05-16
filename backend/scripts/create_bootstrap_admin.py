"""Create or update the first staff admin user (run once on Render Shell).

Requires env:
  BOOTSTRAP_ADMIN_EMAIL
  BOOTSTRAP_ADMIN_PASSWORD

Optional:
  BOOTSTRAP_ADMIN_FIRST_NAME (default Admin)
  BOOTSTRAP_ADMIN_LAST_NAME (default User)

From ``backend/``:
  python scripts/create_bootstrap_admin.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from sqlalchemy import select  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.auth import Role, User, UserRole  # noqa: E402


def _ensure_role(code: str, name: str) -> Role:
    role = db.session.scalar(select(Role).where(Role.code == code))
    if role:
        return role
    role = Role(code=code, name=name, description=f"Bootstrap role: {name}")
    db.session.add(role)
    db.session.flush()
    return role


def main() -> None:
    email = (os.environ.get("BOOTSTRAP_ADMIN_EMAIL") or "").strip().lower()
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD") or ""
    if not email or not password:
        print("Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    if len(password) < 8:
        print("BOOTSTRAP_ADMIN_PASSWORD must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    first = (os.environ.get("BOOTSTRAP_ADMIN_FIRST_NAME") or "Admin").strip() or "Admin"
    last = (os.environ.get("BOOTSTRAP_ADMIN_LAST_NAME") or "User").strip() or "User"

    app = create_app()
    with app.app_context():
        user = db.session.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(
                email=email,
                first_name=first,
                last_name=last,
                is_active=True,
                is_superuser=True,
            )
            db.session.add(user)
            db.session.flush()
            print(f"Created user {email}")
        else:
            user.first_name = first
            user.last_name = last
            user.is_active = True
            user.is_superuser = True
            print(f"Updated user {email}")

        user.password_hash = generate_password_hash(password)

        admin_role = _ensure_role("admin", "Administrator")
        hr_admin_role = _ensure_role("hr_admin", "HR Administrator")

        for role in (admin_role, hr_admin_role):
            exists = db.session.scalar(
                select(UserRole).where(
                    UserRole.user_id == user.id,
                    UserRole.role_id == role.id,
                )
            )
            if not exists:
                db.session.add(UserRole(user_id=user.id, role_id=role.id))

        db.session.commit()
        print("Bootstrap admin ready. Sign in at /page-login.html")


if __name__ == "__main__":
    main()
