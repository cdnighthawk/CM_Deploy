"""REST API for USIS HRMS (embedded HR suite)."""
from __future__ import annotations

from flask import Blueprint, jsonify

from ..api._perms import current_user
from ..extensions import db
from ..models.hrms_core import HrmsEmployeeProfile
from ._audit import write_hrms_audit
from ._dashboard_service import build_dashboard_payload
from ._expense_service import register_expense_routes
from ._perms import can_access_hrms, is_hr_admin, is_hr_manager

hrms_bp = Blueprint("hrms", __name__, url_prefix="/api/v1/hrms")

register_expense_routes(hrms_bp)


def _json_error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


@hrms_bp.get("/dashboard")
def hrms_dashboard():
    cu = current_user()
    if not can_access_hrms(cu):
        return _json_error("Authentication required for HRMS.", 401)
    if is_hr_admin(cu):
        scope = "admin"
    elif is_hr_manager(cu):
        scope = "manager"
    else:
        scope = "employee"
    payload = build_dashboard_payload(scope=scope)
    write_hrms_audit(
        actor_user_id=cu.id,
        action="hrms.dashboard.view",
        entity_type="hrms_dashboard",
        entity_id=None,
        details={"scope": scope},
    )
    db.session.commit()
    return jsonify({"entity": "hrms_dashboard", "item": payload})


@hrms_bp.get("/me/profile")
def hrms_me_profile():
    cu = current_user()
    if not can_access_hrms(cu) or cu.user is None:
        return _json_error("Authentication required.", 401)
    u = cu.user
    prof = db.session.get(HrmsEmployeeProfile, u.id)
    out = {
        "user": {
            "id": str(u.id),
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "phone": u.phone,
            "is_active": u.is_active,
        },
        "profile": None,
    }
    if prof is not None:
        out["profile"] = {
            "org_unit_id": str(prof.org_unit_id) if prof.org_unit_id else None,
            "manager_user_id": str(prof.manager_user_id) if prof.manager_user_id else None,
            "job_title": prof.job_title,
            "hire_date": prof.hire_date.isoformat() if prof.hire_date else None,
            "termination_date": prof.termination_date.isoformat() if prof.termination_date else None,
            "employment_status": prof.employment_status,
            "custom_fields": prof.custom_fields or {},
        }
    return jsonify({"entity": "hrms_me_profile", "item": out})


@hrms_bp.get("/health")
def hrms_health():
    """Cheap probe for operators (no auth)."""
    return jsonify({"status": "ok", "module": "hrms"})
