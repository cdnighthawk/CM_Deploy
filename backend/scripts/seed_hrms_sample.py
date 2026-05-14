"""Seed HRMS reference data (leave types already in migration; roles + sample profile optional).

Run from ``backend/`` with PYTHONPATH set to the backend root, e.g.:

  cd backend
  python scripts/seed_hrms_sample.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models.auth import Role, User, UserRole  # noqa: E402
from sqlalchemy import select  # noqa: E402


def _ensure_role(code: str, name: str) -> Role:
    r = db.session.scalar(select(Role).where(Role.code == code))
    if r:
        return r
    r = Role(code=code, name=name, description=f"HRMS role: {name}")
    db.session.add(r)
    db.session.flush()
    return r


def main() -> None:
    app = create_app()
    with app.app_context():
        for code, name in (
            ("hr_admin", "HR Administrator"),
            ("hr_manager", "HR Manager"),
            ("hr_employee", "HR Employee"),
        ):
            _ensure_role(code, name)
        db.session.commit()
        print("HRMS sample: ensured roles hr_admin, hr_manager, hr_employee exist.")


if __name__ == "__main__":
    main()
