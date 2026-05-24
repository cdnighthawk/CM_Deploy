"""Self-service hire wizard: application JSON + I-9 Section 1 + W-4 policy attestations."""

from __future__ import annotations



import json

import re

import uuid

from datetime import datetime, timezone

from typing import Any



from flask import Blueprint, Response, request

from sqlalchemy import select



from ..extensions import db

from ..models import AuditLog, HrHireApplication, HrOnboardingItem, HrPolicyAcknowledgment, User
from ._hr_i9_documents import list_i9_documents_for_hire, register_hr_i9_document_routes
from ._hr_union_documents import (
    list_union_documents_for_hire,
    register_hr_union_document_routes,
    union_kind_has_photo,
)
from ._hr_w4_documents import list_w4_documents_for_hire, register_hr_w4_document_routes

from ..services.hire_application_mappings import (
    map_application_to_i9_prefill,
    map_application_to_w4_prefill,
    normalize_citizenship_status,
    normalize_date_of_birth,
    normalize_filing_status,
    normalize_ssn,
    sync_i9_w4_drafts_from_application,
)
from ..services.hr_i9_crypto import decrypt_section1, encrypt_section1
from ..services.hr_w4_crypto import decrypt_w4, encrypt_w4

from ..services.hr_hire_signed_forms import (
    persist_signed_i9,
    persist_signed_w4,
    render_i9_preview_html,
    render_w4_preview_html,
    signed_form_staff_url,
)
from ..services.hr_i9_validate import validate_section1
from ..services.hr_w4_validate import validate_w4
from ..services.hire_application_review import (
    TERMINAL_HIRE_STATUSES,
    applicant_wizard_mutable,
    mark_submitted_for_review,
    serialize_hire_status,
    serialize_offer_block,
)
from ..services.hire_path import (
    HIRE_PATH_STANDARD,
    HIRE_PATH_UNION_DISPATCH,
    applicant_may_complete_i9_w4,
    applicant_may_upload_union,
    is_standard_path,
)
from ..services.hr_job_offer import try_auto_hire_after_onboarding
from ._notifications import send_application_approval_letter_email

from ._perms import current_user

from .v1 import _iso, _jsonify



HIRE_WIZARD_ONBOARD_TITLE = "Employment application (hire wizard)"

HIRE_POLICY_I9_VERSION = "hire-federal-i9-attestation-v1"

HIRE_POLICY_W4_VERSION = "hire-federal-w4-attestation-v1"

_HIRE_APPLICATION_ALLOWED_KEYS = frozenset(

    {

        "address_line1",

        "address_line2",

        "certifications_licenses",

        "citizenship_status",

        "city",

        "country",

        "date_of_birth",

        "deductions",

        "dependents_amount",

        "desired_compensation",

        "drivers_license_number",

        "drivers_license_state",

        "education_degree",

        "education_graduation_year",

        "education_level",

        "education_school",

        "emergency_contact_name",

        "emergency_contact_phone",

        "emergency_contact_relationship",

        "employment_history",

        "felony_conviction",

        "felony_explanation",

        "filing_status",

        "how_heard_about_position",

        "middle_initial",

        "other_income",

        "position_applying_for",

        "postal_code",

        "preferred_start_date",

        "prior_employer_summary",

        "requires_sponsorship",

        "signature_certified",

        "signature_date",

        "signature_full_name",

        "skills_experience",

        "ssn",

        "state",

        "work_authorized_us",

        "extra_withholding",

    }

)

_HIRE_APPLICATION_MONEY_KEYS = frozenset(

    {

        "deductions",

        "dependents_amount",

        "extra_withholding",

        "other_income",

    }

)

_HIRE_APPLICATION_CITIZENSHIP_KEYS = frozenset({"citizenship_status"})

_HIRE_APPLICATION_FILING_KEYS = frozenset({"filing_status"})

_HIRE_APPLICATION_TEXTAREA_KEYS = frozenset(

    {

        "certifications_licenses",

        "felony_explanation",

        "prior_employer_summary",

        "skills_experience",

    }

)

_HIRE_APPLICATION_YESNO_KEYS = frozenset(

    {

        "felony_conviction",

        "requires_sponsorship",

        "work_authorized_us",

    }

)

_HIRE_APPLICATION_EMPLOYMENT_KEYS = frozenset(

    {

        "company_name",

        "end_date",

        "job_title",

        "may_contact",

        "reason_for_leaving",

        "start_date",

    }

)

_HIRE_APPLICATION_MAX_JSON = 48_000

_HIRE_APPLICATION_STRING_MAX = 2000

_HIRE_APPLICATION_TEXTAREA_MAX = 8000

_I9_SIGNATURE_MAX_LEN = 600_000
_W4_SIGNATURE_MAX_LEN = 600_000





def _hire_policy_label(version: str) -> str:

    return {

        HIRE_POLICY_I9_VERSION: "Federal Form I-9 — Section 1 (wizard)",

        HIRE_POLICY_W4_VERSION: "Federal Form W-4 — withholding (wizard)",

    }.get(version, version.replace("-", " ").title())





def _client_ip_for_audit() -> str | None:

    xff = request.headers.get("X-Forwarded-For")

    if xff:

        first = xff.split(",")[0].strip()

        if first:

            return first[:64]

    if request.remote_addr:

        return str(request.remote_addr)[:64]

    return None





def _normalize_person_name(s: str) -> str:

    return " ".join(str(s).strip().split()).lower()





def _typed_name_matches_user(typed: str, u: User) -> bool:

    typed_n = _normalize_person_name(typed)

    if not typed_n:

        return False

    official = _normalize_person_name(" ".join(p for p in (u.first_name or "", u.last_name or "") if p))

    if official and typed_n == official:

        return True

    fn = _normalize_person_name(u.first_name or "")

    ln = _normalize_person_name(u.last_name or "")

    if fn and ln:

        return typed_n in (f"{fn} {ln}", f"{ln} {fn}")

    if fn and typed_n == fn:

        return True

    if ln and typed_n == ln:

        return True

    return False





def _sanitize_hire_application_yes_no(raw: Any) -> str | None:

    if raw is None:

        return None

    s = str(raw).strip().lower()

    if s in ("yes", "no"):

        return s

    return None





def _sanitize_hire_application_string(raw: Any, *, max_len: int = _HIRE_APPLICATION_STRING_MAX) -> str | None:

    if raw is None:

        return None

    s = str(raw).strip()

    if len(s) > max_len:

        return None

    return s





def _sanitize_hire_application_employment_history(raw: Any) -> list[dict[str, Any]] | None:

    if raw is None:

        return []

    if not isinstance(raw, list) or len(raw) > 4:

        return None

    out: list[dict[str, Any]] = []

    for item in raw:

        if not isinstance(item, dict):

            return None

        row: dict[str, Any] = {}

        for ek in _HIRE_APPLICATION_EMPLOYMENT_KEYS:

            if ek not in item:

                continue

            ev = item[ek]

            if ev is None:

                row[ek] = None

                continue

            if ek == "may_contact":

                yn = _sanitize_hire_application_yes_no(ev)

                if yn is None and str(ev).strip():

                    return None

                row[ek] = yn

            else:

                s = _sanitize_hire_application_string(ev)

                if s is None and str(ev).strip():

                    return None

                row[ek] = s

        if any(str(row.get(f) or "").strip() for f in ("company_name", "job_title", "start_date", "end_date")):

            out.append(row)

    return out





def _sanitize_hire_application_payload(raw: Any) -> dict[str, Any] | None:

    if not isinstance(raw, dict):

        return None

    out: dict[str, Any] = {}

    for k, v in raw.items():

        if k not in _HIRE_APPLICATION_ALLOWED_KEYS:

            continue

        if k == "employment_history":

            eh = _sanitize_hire_application_employment_history(v)

            if eh is None:

                return None

            out[k] = eh

            continue

        if k == "signature_certified":

            out[k] = bool(v)

            continue

        if k in _HIRE_APPLICATION_YESNO_KEYS:

            if v is None or str(v).strip() == "":

                out[k] = None

                continue

            yn = _sanitize_hire_application_yes_no(v)

            if yn is None:

                return None

            out[k] = yn

            continue

        if k == "ssn":

            if v is None or str(v).strip() == "":

                out[k] = None

                continue

            normalized = normalize_ssn(v)

            if normalized is None:

                return None

            out[k] = normalized

            continue

        if k == "date_of_birth":

            if v is None or str(v).strip() == "":

                out[k] = None

                continue

            out[k] = normalize_date_of_birth(v)

            continue

        if k in _HIRE_APPLICATION_CITIZENSHIP_KEYS:

            if v is None or str(v).strip() == "":

                out[k] = None

                continue

            status = normalize_citizenship_status(v)

            if not status:

                return None

            out[k] = status

            continue

        if k in _HIRE_APPLICATION_FILING_KEYS:

            if v is None or str(v).strip() == "":

                out[k] = None

                continue

            status = normalize_filing_status(v)

            if not status:

                return None

            out[k] = status

            continue

        if k in _HIRE_APPLICATION_MONEY_KEYS:

            if v is None or str(v).strip() == "":

                out[k] = None

                continue

            s = _sanitize_hire_application_string(v, max_len=32)

            if s is None:

                return None

            out[k] = s.replace(",", "").replace("$", "")

            continue

        if v is None:

            out[k] = None

            continue

        max_len = (

            _HIRE_APPLICATION_TEXTAREA_MAX if k in _HIRE_APPLICATION_TEXTAREA_KEYS else _HIRE_APPLICATION_STRING_MAX

        )

        s = _sanitize_hire_application_string(v, max_len=max_len)

        if s is None:

            return None

        out[k] = s

    return out





def _parse_application_json(hire_row: HrHireApplication | None) -> dict[str, Any] | None:

    if hire_row is None or not hire_row.application_json:

        return None

    try:

        data = json.loads(hire_row.application_json)

        return data if isinstance(data, dict) else None

    except json.JSONDecodeError:

        return None





def _build_i9_prefill(u: User, app: dict[str, Any] | None) -> dict[str, Any]:

    return map_application_to_i9_prefill(u, app)





def _i9_status_block(hire_row: HrHireApplication | None) -> dict[str, Any]:

    if hire_row is None:

        return {"status": "not_started", "completed_at": None, "signed_at": None, "locked": False}

    if hire_row.i9_signed_at is not None:

        return {

            "status": "signed",

            "completed_at": _iso(hire_row.i9_section1_completed_at),

            "signed_at": _iso(hire_row.i9_signed_at),

            "locked": True,

        }

    if hire_row.i9_section1_completed_at is not None:

        return {

            "status": "completed",

            "completed_at": _iso(hire_row.i9_section1_completed_at),

            "signed_at": None,

            "locked": False,

        }

    if hire_row.i9_section1_json_encrypted:

        return {

            "status": "draft",

            "completed_at": None,

            "signed_at": None,

            "locked": False,

        }

    return {"status": "not_started", "completed_at": None, "signed_at": None, "locked": False}





def _decrypt_draft_for_owner(hire_row: HrHireApplication | None) -> dict[str, Any] | None:

    if hire_row is None or not hire_row.i9_section1_json_encrypted:

        return None

    try:

        return decrypt_section1(hire_row.i9_section1_json_encrypted)

    except ValueError:

        return None





def _build_w4_prefill(u: User, app: dict[str, Any] | None) -> dict[str, Any]:

    return map_application_to_w4_prefill(u, app)





def _w4_status_block(hire_row: HrHireApplication | None) -> dict[str, Any]:

    if hire_row is None:

        return {"status": "not_started", "completed_at": None, "signed_at": None, "locked": False}

    if hire_row.w4_signed_at is not None:

        return {

            "status": "signed",

            "completed_at": _iso(hire_row.w4_completed_at),

            "signed_at": _iso(hire_row.w4_signed_at),

            "locked": True,

        }

    if hire_row.w4_completed_at is not None:

        return {

            "status": "completed",

            "completed_at": _iso(hire_row.w4_completed_at),

            "signed_at": None,

            "locked": False,

        }

    if hire_row.w4_json_encrypted:

        return {

            "status": "draft",

            "completed_at": None,

            "signed_at": None,

            "locked": False,

        }

    return {"status": "not_started", "completed_at": None, "signed_at": None, "locked": False}





def _decrypt_w4_draft_for_owner(hire_row: HrHireApplication | None) -> dict[str, Any] | None:

    if hire_row is None or not hire_row.w4_json_encrypted:

        return None

    try:

        return decrypt_w4(hire_row.w4_json_encrypted)

    except ValueError:

        return None





def _ensure_hire_wizard_rows(user_id: uuid.UUID) -> None:

    exists_ob = db.session.scalar(

        select(HrOnboardingItem.id).where(

            HrOnboardingItem.user_id == user_id,

            HrOnboardingItem.title == HIRE_WIZARD_ONBOARD_TITLE,

        )

    )

    if exists_ob is None:

        db.session.add(

            HrOnboardingItem(

                user_id=user_id,

                title=HIRE_WIZARD_ONBOARD_TITLE,

                sort_order=-100,

            )

        )

    for pv in (HIRE_POLICY_I9_VERSION, HIRE_POLICY_W4_VERSION):

        exists_pol = db.session.scalar(

            select(HrPolicyAcknowledgment.id).where(

                HrPolicyAcknowledgment.user_id == user_id,

                HrPolicyAcknowledgment.policy_version == pv,

            )

        )

        if exists_pol is None:

            db.session.add(HrPolicyAcknowledgment(user_id=user_id, policy_version=pv, signed_at=None))

    db.session.commit()





def _get_or_create_hire_row(uid: uuid.UUID) -> HrHireApplication:

    hire_row = db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))

    if hire_row is None:

        hire_row = HrHireApplication(user_id=uid)

        db.session.add(hire_row)

        db.session.flush()

    return hire_row





def _wizard_mutable_guard(hire_row: HrHireApplication | None):
    if not applicant_wizard_mutable(hire_row):
        return _jsonify(
            {
                "entity": "hr_hire_wizard",
                "error": "application closed",
                "message": "This application is no longer open for editing.",
            }
        ), 409
    return None


def _require_hire_path(hire_row: HrHireApplication | None):
    if hire_row is None or not hire_row.hire_path:
        return _jsonify(
            {
                "entity": "hr_hire_wizard",
                "error": "hire path required",
                "message": "Answer the onboarding question before continuing.",
            }
        ), 403
    return None


def _require_i9_w4_eligible(hire_row: HrHireApplication | None):
    missing = _require_hire_path(hire_row)
    if missing is not None:
        return missing
    if not applicant_may_complete_i9_w4(hire_row):
        return _jsonify(
            {
                "entity": "hr_hire_wizard",
                "error": "I-9 and W-4 not available yet",
                "message": "Complete earlier steps or accept your job offer before Form I-9 and W-4.",
            }
        ), 403
    return None


def _require_i9_w4_draft_save(hire_row: HrHireApplication | None):
    missing = _require_hire_path(hire_row)
    if missing is not None:
        return missing
    if hire_row is not None and hire_row.submitted_at is not None:
        return None
    return _require_i9_w4_eligible(hire_row)


def _build_hire_tasks(
    *,
    hire_row: HrHireApplication | None,
    steps: dict[str, Any],
    i9_status: str,
    w4_status: str,
) -> dict[str, Any]:
    """Checklist for the hire wizard UI (status + lock rules).

    Dependency order (enforced in UI; W-4 sign also requires I-9 signed on the server):
      account → application → Form I-9 → Form W-4 → union docs (optional).
    """

    app_done = bool((steps.get("application") or {}).get("completed"))
    i9_signed = i9_status == "signed"
    w4_signed = w4_status == "signed"
    hire_locked = hire_row is not None and hire_row.hire_status in TERMINAL_HIRE_STATUSES
    hire_path = hire_row.hire_path if hire_row else None
    standard = hire_path == HIRE_PATH_STANDARD
    union_path = hire_path == HIRE_PATH_UNION_DISPATCH
    i9_eligible = applicant_may_complete_i9_w4(hire_row)
    offer_pending = bool(
        hire_row
        and standard
        and hire_row.hire_status == "offer_extended"
    )
    offer_accepted = bool(hire_row and hire_row.offer_accepted_at)

    def _app_task_status() -> str:
        if app_done:
            return "complete"
        if hire_row is not None and hire_row.application_json:
            return "in_progress"
        return "not_started"

    def _union_task_status(kind: str) -> str:
        if union_kind_has_photo(hire_row, kind):
            return "complete"
        return "not_started"

    def _i9_task_status() -> str:
        if i9_signed:
            return "complete"
        if i9_status in ("completed", "draft"):
            return "in_progress"
        return "not_started"

    def _w4_task_status() -> str:
        if w4_signed:
            return "complete"
        if w4_status in ("completed", "draft"):
            return "in_progress"
        return "not_started"

    tasks: list[dict[str, Any]] = [
        {
            "key": "account",
            "title": "Create your USIS account",
            "description": "Sign in or register so your hire progress is saved.",
            "status": "complete",
            "locked": False,
            "prerequisite": None,
        },
        {
            "key": "application",
            "title": "Employment application",
            "description": "Profile, contact, position details, and employment history.",
            "status": _app_task_status(),
            "locked": False,
            "prerequisite": "account",
        },
        {
            "key": "i9",
            "title": "Form I-9 — Section 1",
            "description": "USCIS employment eligibility and identity (Section 1 + e-sign).",
            "status": _i9_task_status(),
            "locked": not app_done or not i9_eligible,
            "prerequisite": "application" if union_path else "offer",
            "hidden": standard and not offer_accepted and not i9_signed,
        },
        {
            "key": "w4",
            "title": "Form W-4 — withholding",
            "description": "Federal income tax withholding elections and e-sign.",
            "status": _w4_task_status(),
            "locked": not i9_signed or not i9_eligible,
            "prerequisite": "i9",
            "hidden": standard and not offer_accepted and not w4_signed,
        },
        {
            "key": "union_card",
            "title": "Union card",
            "description": "Optional photo of your union membership card.",
            "status": _union_task_status("union_card"),
            "locked": not w4_signed or hire_locked or not union_path,
            "prerequisite": "w4",
            "optional": True,
            "hidden": not union_path,
        },
        {
            "key": "union_dispatch",
            "title": "Union dispatch",
            "description": "Optional photo of your union dispatch slip or paperwork.",
            "status": _union_task_status("union_dispatch"),
            "locked": not w4_signed or hire_locked or not union_path,
            "prerequisite": "w4",
            "optional": True,
            "hidden": not union_path,
        },
        {
            "key": "offer",
            "title": "Job offer",
            "description": "Review and accept your job offer from DOCOM, INC.",
            "status": "complete" if offer_accepted else ("in_progress" if offer_pending else "not_started"),
            "locked": not app_done or not standard,
            "prerequisite": "application",
            "hidden": not standard,
        },
    ]

    required_tasks = [t for t in tasks if not t.get("optional") and not t.get("hidden")]
    completed = sum(1 for t in required_tasks if t["status"] == "complete")
    total = len(required_tasks)
    percent = int(round(100 * completed / total)) if total else 0

    return {"tasks": tasks, "progress": {"completed": completed, "total": total, "percent": percent}}


def register_hr_hire_wizard_routes(bp: Blueprint) -> None:

    @bp.get("/hr/me/hire-wizard")

    def hr_me_hire_wizard():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_hire_wizard", "error": "authentication required"}), 401

        uid = cu.user.id

        _ensure_hire_wizard_rows(uid)

        u = db.session.get(User, uid)

        assert u is not None

        hire_row = db.session.scalar(select(HrHireApplication).where(HrHireApplication.user_id == uid))

        app_payload = _parse_application_json(hire_row)

        app_submitted = _iso(hire_row.submitted_at) if hire_row else None



        ob = db.session.scalar(

            select(HrOnboardingItem).where(

                HrOnboardingItem.user_id == uid,

                HrOnboardingItem.title == HIRE_WIZARD_ONBOARD_TITLE,

            )

        )

        pol_i9 = db.session.scalar(

            select(HrPolicyAcknowledgment).where(

                HrPolicyAcknowledgment.user_id == uid,

                HrPolicyAcknowledgment.policy_version == HIRE_POLICY_I9_VERSION,

            )

        )

        pol_w4 = db.session.scalar(

            select(HrPolicyAcknowledgment).where(

                HrPolicyAcknowledgment.user_id == uid,

                HrPolicyAcknowledgment.policy_version == HIRE_POLICY_W4_VERSION,

            )

        )

        i9_draft = _decrypt_draft_for_owner(hire_row)

        w4_draft = _decrypt_w4_draft_for_owner(hire_row)

        steps_block = {

            "application": {

                "onboarding_item_id": str(ob.id) if ob else None,

                "completed": (

                    (ob.completed_at is not None if ob else False)

                    or (hire_row is not None and hire_row.submitted_at is not None)

                ),

            },

            "i9": {

                "policy_acknowledgment_id": str(pol_i9.id) if pol_i9 else None,

                "signed_at": _iso(pol_i9.signed_at) if pol_i9 else None,

                "policy_title": _hire_policy_label(HIRE_POLICY_I9_VERSION),

                **{k: v for k, v in _i9_status_block(hire_row).items() if k != "locked"},

            },

            "w4": {

                "policy_acknowledgment_id": str(pol_w4.id) if pol_w4 else None,

                "signed_at": _iso(pol_w4.signed_at) if pol_w4 else None,

                "policy_title": _hire_policy_label(HIRE_POLICY_W4_VERSION),

                **{k: v for k, v in _w4_status_block(hire_row).items() if k != "locked"},

            },

        }

        i9_st = _i9_status_block(hire_row)["status"]

        w4_st = _w4_status_block(hire_row)["status"]

        union_docs = list_union_documents_for_hire(hire_row)

        union_locked = (
            hire_row is None
            or hire_row.hire_path != HIRE_PATH_UNION_DISPATCH
            or hire_row.w4_signed_at is None
            or hire_row.hire_status in TERMINAL_HIRE_STATUSES
        )

        checklist = _build_hire_tasks(

            hire_row=hire_row,

            steps=steps_block,

            i9_status=i9_st,

            w4_status=w4_st,

        )

        return _jsonify(

            {

                "entity": "hr_hire_wizard",

                "disclaimer": (

                    "This wizard collects hire intake, I-9 Section 1, and Form W-4 withholding for USIS onboarding. "

                    "Your employer must still retain compliant Form I-9 and official W-4 records per federal rules. "

                    "Social Security numbers are encrypted at rest."

                ),

                "official_links": {

                    "i9_instructions": "https://www.uscis.gov/i-9",

                    "i9_pdf": "https://www.uscis.gov/sites/default/files/document/forms/i-9.pdf",

                    "w4_pdf": "https://www.irs.gov/pub/irs-pdf/fw4.pdf",

                },

                "user": {

                    "id": str(u.id),

                    "email": u.email,

                    "first_name": u.first_name,

                    "last_name": u.last_name,

                    "phone": u.phone,

                },

                "application": {"submitted_at": app_submitted, "payload": app_payload},

                "hire_path": hire_row.hire_path if hire_row else None,

                "path_selection_required": hire_row is None or not hire_row.hire_path,

                "offer": serialize_offer_block(hire_row),

                "review": serialize_hire_status(hire_row),

                "i9": {

                    "prefill": _build_i9_prefill(u, app_payload),

                    "draft": i9_draft,

                    "documents": list_i9_documents_for_hire(hire_row),

                    **_i9_status_block(hire_row),

                },

                "w4": {

                    "prefill": _build_w4_prefill(u, app_payload),

                    "draft": w4_draft,

                    "documents": list_w4_documents_for_hire(hire_row),

                    **_w4_status_block(hire_row),

                },

                "union": {

                    "documents": union_docs,

                    "locked": union_locked,

                },

                "steps": steps_block,

                "tasks": checklist["tasks"],

                "progress": checklist["progress"],

            }

        )



    @bp.post("/hr/me/hire-application")

    def hr_me_hire_application():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_hire_application", "error": "authentication required"}), 401

        uid = cu.user.id

        _ensure_hire_wizard_rows(uid)

        body = request.get_json(silent=True) or {}

        if not isinstance(body, dict):

            return _jsonify({"entity": "hr_hire_application", "error": "JSON body required"}), 400

        sanitized = _sanitize_hire_application_payload(body.get("application"))

        if sanitized is None:

            return _jsonify({"entity": "hr_hire_application", "error": "invalid application payload"}), 400

        dumped = json.dumps(sanitized, separators=(",", ":"), ensure_ascii=False)

        if len(dumped) > _HIRE_APPLICATION_MAX_JSON:

            return _jsonify({"entity": "hr_hire_application", "error": "application too large"}), 400

        hire_row = _get_or_create_hire_row(uid)

        blocked = _wizard_mutable_guard(hire_row)
        if blocked is not None:
            return blocked

        from ..services.hire_application_review import applicant_may_edit_application

        if not applicant_may_edit_application(hire_row):
            return _jsonify({"entity": "hr_hire_application", "error": "application is locked"}), 409

        path_block = _require_hire_path(hire_row)
        if path_block is not None:
            return path_block

        now = datetime.now(timezone.utc)

        hire_row.application_json = dumped

        hire_row.submitted_at = now

        mark_submitted_for_review(hire_row, when=now)

        ob = db.session.scalar(

            select(HrOnboardingItem).where(

                HrOnboardingItem.user_id == uid,

                HrOnboardingItem.title == HIRE_WIZARD_ONBOARD_TITLE,

            )

        )

        if ob is not None:

            ob.completed_at = now

        sync_i9_w4_drafts_from_application(hire_row, cu.user)

        db.session.commit()

        return _jsonify({"entity": "hr_hire_application", "ok": True, "submitted_at": _iso(now)})



    @bp.post("/hr/me/i9-section1")

    def hr_me_i9_section1_save():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_i9_section1", "error": "authentication required"}), 401

        uid = cu.user.id

        _ensure_hire_wizard_rows(uid)

        hire_row = _get_or_create_hire_row(uid)

        blocked = _wizard_mutable_guard(hire_row)
        if blocked is not None:
            return blocked

        eligible = _require_i9_w4_draft_save(hire_row)
        if eligible is not None:
            return eligible

        if hire_row.i9_signed_at is not None:

            return _jsonify({"entity": "hr_i9_section1", "error": "I-9 is signed and locked"}), 409

        body = request.get_json(silent=True) or {}

        if not isinstance(body, dict):

            return _jsonify({"entity": "hr_i9_section1", "error": "JSON body required"}), 400

        raw = body.get("section1")

        sanitized, errors = validate_section1(raw)

        if errors:

            return _jsonify({"entity": "hr_i9_section1", "error": "validation failed", "details": errors}), 400

        assert sanitized is not None

        mark_complete = body.get("mark_complete") is True

        now = datetime.now(timezone.utc)

        hire_row.i9_section1_json_encrypted = encrypt_section1(sanitized)

        if mark_complete:

            hire_row.i9_section1_completed_at = now

        db.session.commit()

        return _jsonify(

            {

                "entity": "hr_i9_section1",

                "ok": True,

                "completed_at": _iso(hire_row.i9_section1_completed_at),

                "status": _i9_status_block(hire_row)["status"],

            }

        )



    @bp.get("/hr/me/i9-section1/preview")

    def hr_me_i9_section1_preview():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_i9_preview", "error": "authentication required"}), 401

        uid = cu.user.id

        hire_row = _get_or_create_hire_row(uid)

        section1 = _decrypt_draft_for_owner(hire_row)

        if not section1:

            return _jsonify({"entity": "hr_i9_preview", "error": "no saved Section 1 to preview"}), 404

        eligible = _require_i9_w4_draft_save(hire_row)
        if eligible is not None:
            return eligible

        html = render_i9_preview_html(user=cu.user, section1=section1, hire_row=hire_row)

        return Response(html, mimetype="text/html")



    @bp.post("/hr/me/i9-section1/sign")

    def hr_me_i9_section1_sign():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_i9_sign", "error": "authentication required"}), 401

        uid = cu.user.id

        _ensure_hire_wizard_rows(uid)

        hire_row = _get_or_create_hire_row(uid)

        blocked = _wizard_mutable_guard(hire_row)
        if blocked is not None:
            return blocked

        eligible = _require_i9_w4_eligible(hire_row)
        if eligible is not None:
            return eligible

        if hire_row.i9_signed_at is not None:

            return _jsonify({"entity": "hr_i9_sign", "error": "I-9 already signed"}), 409

        if not hire_row.i9_section1_json_encrypted:

            return _jsonify({"entity": "hr_i9_sign", "error": "complete Section 1 before signing"}), 400

        if hire_row.i9_section1_completed_at is None:

            return _jsonify({"entity": "hr_i9_sign", "error": "mark Section 1 complete before signing"}), 400

        body = request.get_json(silent=True) or {}

        if not isinstance(body, dict):

            return _jsonify({"entity": "hr_i9_sign", "error": "JSON body required"}), 400

        if body.get("certify") is not True:

            return _jsonify({"entity": "hr_i9_sign", "error": "certify must be true"}), 400

        typed = str(body.get("typed_full_name") or "").strip()

        u = db.session.get(User, uid)

        assert u is not None

        if not _typed_name_matches_user(typed, u):

            return _jsonify(

                {

                    "entity": "hr_i9_sign",

                    "error": "typed name does not match your account name; update Profile or type exactly as shown.",

                }

            ), 400

        sig = str(body.get("signature_png_base64") or "").strip()

        if not sig:

            return _jsonify({"entity": "hr_i9_sign", "error": "signature_png_base64 is required"}), 400

        if len(sig) > _I9_SIGNATURE_MAX_LEN:

            return _jsonify({"entity": "hr_i9_sign", "error": "signature image too large"}), 400

        if not re.match(r"^data:image/png;base64,", sig) and not re.match(r"^[A-Za-z0-9+/=]+$", sig[:200]):

            return _jsonify({"entity": "hr_i9_sign", "error": "invalid signature format"}), 400



        try:

            section1 = decrypt_section1(hire_row.i9_section1_json_encrypted)

        except ValueError:

            return _jsonify({"entity": "hr_i9_sign", "error": "stored I-9 data is invalid"}), 500



        pol_i9 = db.session.scalar(

            select(HrPolicyAcknowledgment).where(

                HrPolicyAcknowledgment.user_id == uid,

                HrPolicyAcknowledgment.policy_version == HIRE_POLICY_I9_VERSION,

            )

        )

        now = datetime.now(timezone.utc)

        hire_row.i9_signature_png = sig if sig.startswith("data:") else f"data:image/png;base64,{sig}"

        hire_row.i9_signed_at = now
        section1["signature_date"] = now.date().isoformat()
        hire_row.i9_section1_json_encrypted = encrypt_section1(section1)

        ip = _client_ip_for_audit()

        if pol_i9 is not None and pol_i9.signed_at is None:

            pol_i9.signed_at = now

            pol_i9.ip_address = ip

        db.session.add(

            AuditLog(

                user_id=uid,

                entity_type="hr_hire_i9",

                entity_id=hire_row.id,

                action="i9_signed",

                ip_address=ip,

                message="Employee signed I-9 Section 1 in hire wizard",

            )

        )

        persist_signed_i9(
            hire_row=hire_row,
            user=u,
            section1=section1,
            signature_png=hire_row.i9_signature_png,
            signed_at=now,
            typed_full_name=typed,
            api_path=signed_form_staff_url(uid, "i9"),
        )

        db.session.commit()

        return _jsonify(

            {

                "entity": "hr_i9_sign",

                "ok": True,

                "signed_at": _iso(hire_row.i9_signed_at),

                "policy_version": HIRE_POLICY_I9_VERSION,

                "signed_document_url": signed_form_staff_url(uid, "i9"),

            }

        )



    @bp.post("/hr/me/policy-acknowledgments/<uuid:ack_id>/sign")

    def hr_me_policy_ack_sign(ack_id: uuid.UUID):

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_policy_sign", "error": "authentication required"}), 401

        uid = cu.user.id

        body = request.get_json(silent=True) or {}

        if not isinstance(body, dict):

            return _jsonify({"entity": "hr_policy_sign", "error": "JSON body required"}), 400

        if body.get("certify") is not True:

            return _jsonify({"entity": "hr_policy_sign", "error": "certify must be true"}), 400

        typed = str(body.get("typed_full_name") or "").strip()

        u = db.session.get(User, uid)

        assert u is not None

        if not _typed_name_matches_user(typed, u):

            return _jsonify(

                {

                    "entity": "hr_policy_sign",

                    "error": "typed name does not match your account name; update Profile or type exactly as shown.",

                }

            ), 400

        row = db.session.get(HrPolicyAcknowledgment, ack_id)

        if row is None or row.user_id != uid:

            return _jsonify({"entity": "hr_policy_sign", "error": "not found"}), 404

        if row.policy_version == HIRE_POLICY_I9_VERSION:

            return _jsonify(

                {

                    "entity": "hr_policy_sign",

                    "error": "use POST /hr/me/i9-section1/sign for Form I-9",

                }

            ), 400

        if row.policy_version == HIRE_POLICY_W4_VERSION:

            return _jsonify(

                {

                    "entity": "hr_policy_sign",

                    "error": "use POST /hr/me/w4/sign for Form W-4",

                }

            ), 400

        return _jsonify({"entity": "hr_policy_sign", "error": "policy cannot be signed from this wizard"}), 400

        if row.approval_request_id is not None:

            return _jsonify({"entity": "hr_policy_sign", "error": "pending approval workflow"}), 400

        now = datetime.now(timezone.utc)

        if row.signed_at is None:

            row.signed_at = now

            row.ip_address = _client_ip_for_audit()

        db.session.commit()

        return _jsonify(

            {

                "entity": "hr_policy_sign",

                "ok": True,

                "policy_version": row.policy_version,

                "signed_at": _iso(row.signed_at),

            }

        )

    @bp.post("/hr/me/w4")

    def hr_me_w4_save():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_w4", "error": "authentication required"}), 401

        uid = cu.user.id

        _ensure_hire_wizard_rows(uid)

        hire_row = _get_or_create_hire_row(uid)

        blocked = _wizard_mutable_guard(hire_row)
        if blocked is not None:
            return blocked

        eligible = _require_i9_w4_draft_save(hire_row)
        if eligible is not None:
            return eligible

        if hire_row.w4_signed_at is not None:

            return _jsonify({"entity": "hr_w4", "error": "W-4 is signed and locked"}), 409

        body = request.get_json(silent=True) or {}

        if not isinstance(body, dict):

            return _jsonify({"entity": "hr_w4", "error": "JSON body required"}), 400

        raw = body.get("w4")

        sanitized, errors = validate_w4(raw)

        if errors:

            return _jsonify({"entity": "hr_w4", "error": "validation failed", "details": errors}), 400

        assert sanitized is not None

        mark_complete = body.get("mark_complete") is True

        now = datetime.now(timezone.utc)

        hire_row.w4_json_encrypted = encrypt_w4(sanitized)

        if mark_complete:

            hire_row.w4_completed_at = now

        db.session.commit()

        return _jsonify(

            {

                "entity": "hr_w4",

                "ok": True,

                "completed_at": _iso(hire_row.w4_completed_at),

                "status": _w4_status_block(hire_row)["status"],

            }

        )



    @bp.get("/hr/me/w4/preview")

    def hr_me_w4_preview():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_w4_preview", "error": "authentication required"}), 401

        uid = cu.user.id

        hire_row = _get_or_create_hire_row(uid)

        w4 = _decrypt_w4_draft_for_owner(hire_row)

        if not w4:

            return _jsonify({"entity": "hr_w4_preview", "error": "no saved W-4 to preview"}), 404

        eligible = _require_i9_w4_draft_save(hire_row)
        if eligible is not None:
            return eligible

        html = render_w4_preview_html(user=cu.user, w4=w4, hire_row=hire_row)

        return Response(html, mimetype="text/html")



    @bp.post("/hr/me/w4/sign")

    def hr_me_w4_sign():

        cu = current_user()

        if cu.user is None:

            return _jsonify({"entity": "hr_w4_sign", "error": "authentication required"}), 401

        uid = cu.user.id

        _ensure_hire_wizard_rows(uid)

        hire_row = _get_or_create_hire_row(uid)

        blocked = _wizard_mutable_guard(hire_row)
        if blocked is not None:
            return blocked

        eligible = _require_i9_w4_eligible(hire_row)
        if eligible is not None:
            return eligible

        if hire_row.w4_signed_at is not None:

            return _jsonify({"entity": "hr_w4_sign", "error": "W-4 already signed"}), 409

        if hire_row.i9_signed_at is None:

            return _jsonify({"entity": "hr_w4_sign", "error": "complete and sign Form I-9 before W-4"}), 400

        if not hire_row.w4_json_encrypted:

            return _jsonify({"entity": "hr_w4_sign", "error": "complete W-4 before signing"}), 400

        if hire_row.w4_completed_at is None:

            return _jsonify({"entity": "hr_w4_sign", "error": "mark W-4 complete before signing"}), 400

        body = request.get_json(silent=True) or {}

        if not isinstance(body, dict):

            return _jsonify({"entity": "hr_w4_sign", "error": "JSON body required"}), 400

        if body.get("certify") is not True:

            return _jsonify({"entity": "hr_w4_sign", "error": "certify must be true"}), 400

        typed = str(body.get("typed_full_name") or "").strip()

        u = db.session.get(User, uid)

        assert u is not None

        if not _typed_name_matches_user(typed, u):

            return _jsonify(

                {

                    "entity": "hr_w4_sign",

                    "error": "typed name does not match your account name; update Profile or type exactly as shown.",

                }

            ), 400

        sig = str(body.get("signature_png_base64") or "").strip()

        if not sig:

            return _jsonify({"entity": "hr_w4_sign", "error": "signature_png_base64 is required"}), 400

        if len(sig) > _W4_SIGNATURE_MAX_LEN:

            return _jsonify({"entity": "hr_w4_sign", "error": "signature image too large"}), 400

        if not re.match(r"^data:image/png;base64,", sig) and not re.match(r"^[A-Za-z0-9+/=]+$", sig[:200]):

            return _jsonify({"entity": "hr_w4_sign", "error": "invalid signature format"}), 400

        try:

            draft = decrypt_w4(hire_row.w4_json_encrypted)

        except ValueError:

            return _jsonify({"entity": "hr_w4_sign", "error": "stored W-4 data is invalid"}), 500

        draft["signature_date"] = datetime.now(timezone.utc).date().isoformat()

        hire_row.w4_json_encrypted = encrypt_w4(draft)

        pol_w4 = db.session.scalar(

            select(HrPolicyAcknowledgment).where(

                HrPolicyAcknowledgment.user_id == uid,

                HrPolicyAcknowledgment.policy_version == HIRE_POLICY_W4_VERSION,

            )

        )

        now = datetime.now(timezone.utc)

        hire_row.w4_signature_png = sig if sig.startswith("data:") else f"data:image/png;base64,{sig}"

        hire_row.w4_signed_at = now

        mark_submitted_for_review(hire_row, when=now)

        ip = _client_ip_for_audit()

        if pol_w4 is not None and pol_w4.signed_at is None:

            pol_w4.signed_at = now

            pol_w4.ip_address = ip

        db.session.add(

            AuditLog(

                user_id=uid,

                entity_type="hr_hire_w4",

                entity_id=hire_row.id,

                action="w4_signed",

                ip_address=ip,

                message="Employee signed Form W-4 in hire wizard",

            )

        )

        persist_signed_w4(
            hire_row=hire_row,
            user=u,
            w4=draft,
            signature_png=hire_row.w4_signature_png,
            signed_at=now,
            typed_full_name=typed,
            api_path=signed_form_staff_url(uid, "w4"),
        )

        auto_hired = try_auto_hire_after_onboarding(hire_row=hire_row, user=u)

        db.session.commit()

        if auto_hired:
            send_application_approval_letter_email(user=u, hire_row=hire_row)

        return _jsonify(

            {

                "entity": "hr_w4_sign",

                "ok": True,

                "signed_at": _iso(hire_row.w4_signed_at),

                "policy_version": HIRE_POLICY_W4_VERSION,

                "signed_document_url": signed_form_staff_url(uid, "w4"),

                "auto_hired": auto_hired,

                "hire_status": hire_row.hire_status,

            }

        )



    register_hr_i9_document_routes(bp)

    register_hr_w4_document_routes(bp)

    register_hr_union_document_routes(bp)


