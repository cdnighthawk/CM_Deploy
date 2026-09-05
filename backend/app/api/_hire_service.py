"""People → Hiring packet service.

Mapping (do not clone User):
  Employee directory     → User (backend/app/models/auth.py)
  Time / clock           → EmployeeTimeProfile
  Hire PII / tax / I-9   → HirePacket + children (this module)
  Workflow               → process_key = new_hire (frozen at invite)
  Public token page      → /public/hire/<token> (RFP cousin)
  Documents              → UploadCategory.HR_HIRE under hr/hires/<packet_id>/
  QuickBooks             → no EmployeeAdd; optional ListID paste only
"""
from __future__ import annotations

import csv
import hashlib
import io
import ipaddress
import json
import secrets
import uuid
import zipfile
from datetime import date, datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app, render_template, request
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from ..extensions import db
from ..models import AuditLog, EmployeeTimeProfile, User
from ..models.hiring import (
    FormTemplate,
    HireArtifact,
    HireCompanySetting,
    HireDirectDeposit,
    HireEmergencyContact,
    HireI9,
    HireI9Document,
    HireNoticeAck,
    HirePacket,
    HirePerson,
    HireSignature,
    HireTaxElection,
)
from ..services.hire_crypto import decrypt_str, encrypt_str, hash_token, last4
from ..services.hire_forms import (
    CERT_TEXT,
    DD_AUTH_KEY,
    DE4_KEY,
    DEFAULT_SETTINGS,
    FORM_PACK_VERSION,
    I9_KEY,
    NOTICE_KEYS,
    PAYROLL_GATE_LABELS,
    W4_EXEMPT_TEXT,
    W4_KEY,
    W4_STEP_WORDING,
    default_template_ids,
    ensure_form_templates,
)
from ..services.hire_pdf import (
    render_de4,
    render_de34,
    render_dd_auth,
    render_i9,
    render_notice_placeholder,
    render_notices,
    render_w4,
    sha256_bytes,
)
from ..services.hire_validate import aba_routing_valid, normalize_routing, normalize_ssn
from ..services.object_storage import UploadCategory, read_stored_bytes, save_upload
from ._perms import CurrentUser
from . import _workflow_service as wf

LA = ZoneInfo("America/Los_Angeles")
PROCESS_NEW_HIRE = "new_hire"
SUBJECT_HIRE = "hire_packet"

_PUBLIC_FORBIDDEN = frozenset(
    {
        "user_id",
        "pay_rate_display",
        "pay_rate",
        "fein",
        "employer_fein",
        "start_of_work_date",
        "employment_class",
        "requires_e_verify",
        "primary_project_id",
        "qb_list_id",
        "section2",
        "i9_section2",
    }
)

_RATE: dict[str, list[float]] = {}


class HireApiError(Exception):
    def __init__(self, message: str, status: int = 400, extra: dict[str, Any] | None = None):
        self.message = message
        self.status = status
        self.extra = extra or {}


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _today_la() -> date:
    return datetime.now(tz=LA).date()


def _iso(dt: datetime | date | None) -> str | None:
    if dt is None:
        return None
    if isinstance(dt, datetime):
        return dt.isoformat()
    return dt.isoformat()


def is_hr_full(cu: CurrentUser) -> bool:
    if cu.is_dev_admin:
        return True
    return cu.has_role("admin", "superuser", "hr_admin", "payroll_admin", "executive")


def require_hr_full(cu: CurrentUser) -> None:
    if cu.user is None and not cu.is_dev_admin:
        raise HireApiError("authentication required", 401)
    if not is_hr_full(cu):
        raise HireApiError("HR or payroll admin required", 403)


def _client_ip() -> str | None:
    forwarded = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
    raw = forwarded or (request.remote_addr or "")
    try:
        ipaddress.ip_address(raw)
        return raw
    except ValueError:
        return raw[:45] or None


def _audit(
    *,
    cu: CurrentUser | None,
    packet: HirePacket | None,
    action: str,
    message: str,
    changes: dict[str, Any] | None = None,
) -> None:
    safe = _scrub_pii(changes)
    db.session.add(
        AuditLog(
            user_id=cu.id if cu else None,
            entity_type="hire_packet",
            entity_id=packet.id if packet else None,
            action=action,
            message=message,
            changes=safe,
            ip_address=_client_ip(),
            user_agent=(request.user_agent.string or "")[:500] if request else None,
        )
    )


def _scrub_pii(changes: dict[str, Any] | None) -> dict[str, Any] | None:
    if not changes:
        return None
    banned = ("ssn", "social", "routing", "account_number", "account", "dob", "fein", "edd")
    out: dict[str, Any] = {}
    for k, v in changes.items():
        lk = str(k).lower()
        if any(b in lk for b in banned):
            continue
        if isinstance(v, dict):
            out[k] = _scrub_pii(v)
        else:
            out[k] = v
    return out


def _legal_name(person: HirePerson | None) -> str:
    if person is None:
        return ""
    parts = [person.legal_first, person.legal_middle, person.legal_last, person.legal_suffix]
    return " ".join(p for p in parts if p).strip()


def _display_name(packet: HirePacket) -> str:
    person = packet.person
    if person and person.preferred_name:
        last = person.legal_last or ""
        return f"{person.preferred_name} {last}".strip()
    name = _legal_name(person)
    if name:
        return name
    return (packet.invite_email or "New hire").strip()


def add_business_days(start: date, days: int) -> date:
    cur = start
    added = 0
    while added < days:
        cur += timedelta(days=1)
        if cur.weekday() < 5:
            added += 1
    return cur


def i9_section2_due(start: date | None) -> date | None:
    if start is None:
        return None
    return add_business_days(start, 3)


def setting(key: str, default: str = "") -> str:
    ensure_settings()
    row = db.session.get(HireCompanySetting, key)
    if row is None or not row.value_text:
        return default
    if row.is_secret:
        try:
            return decrypt_str(row.value_text) or default
        except ValueError:
            return default
    return row.value_text


def ensure_settings() -> None:
    for key, (val, secret) in DEFAULT_SETTINGS.items():
        row = db.session.get(HireCompanySetting, key)
        if row is None:
            stored = encrypt_str(val) if secret and val else val
            db.session.add(HireCompanySetting(key=key, value_text=stored, is_secret=secret))
    db.session.flush()


def get_settings_public(*, reveal_secrets: bool = False) -> dict[str, Any]:
    ensure_settings()
    out: dict[str, Any] = {}
    for key, (_val, secret) in DEFAULT_SETTINGS.items():
        row = db.session.get(HireCompanySetting, key)
        raw = row.value_text if row else ""
        if secret:
            plain = ""
            if raw:
                try:
                    plain = decrypt_str(raw) or ""
                except ValueError:
                    plain = ""
            if reveal_secrets:
                out[key] = plain
            else:
                out[key] = last4(plain) if plain else ""
                out[f"{key}_set"] = bool(plain)
        else:
            out[key] = raw or ""
    return out


def patch_settings(data: dict[str, Any], cu: CurrentUser) -> dict[str, Any]:
    require_hr_full(cu)
    ensure_settings()
    for key, (_val, secret) in DEFAULT_SETTINGS.items():
        if key not in data:
            continue
        row = db.session.get(HireCompanySetting, key)
        if row is None:
            row = HireCompanySetting(key=key, is_secret=secret)
            db.session.add(row)
        text = "" if data[key] is None else str(data[key])
        row.is_secret = secret
        row.value_text = encrypt_str(text) if secret else text
    _audit(cu=cu, packet=None, action="settings", message="Updated hire company settings")
    db.session.commit()
    return get_settings_public(reveal_secrets=False)


def _packet_query():
    return select(HirePacket).options(
        selectinload(HirePacket.person),
        selectinload(HirePacket.i9).selectinload(HireI9.documents),
        selectinload(HirePacket.direct_deposit),
        selectinload(HirePacket.tax_elections),
        selectinload(HirePacket.emergency_contacts),
        selectinload(HirePacket.notice_acks),
        selectinload(HirePacket.signatures),
        selectinload(HirePacket.artifacts),
    )


def get_packet(pid: uuid.UUID) -> HirePacket:
    row = db.session.scalars(_packet_query().where(HirePacket.id == pid)).first()
    if row is None:
        raise HireApiError("hire packet not found", 404)
    return row


def _tax(packet: HirePacket, form_key: str) -> HireTaxElection | None:
    rows = [t for t in (packet.tax_elections or []) if t.form_key == form_key]
    if not rows:
        return None
    return max(rows, key=lambda r: r.version)


def _ensure_person(packet: HirePacket) -> HirePerson:
    if packet.person is None:
        packet.person = HirePerson(packet_id=packet.id)
        db.session.add(packet.person)
        db.session.flush()
    return packet.person


def _ensure_i9(packet: HirePacket) -> HireI9:
    if packet.i9 is None:
        packet.i9 = HireI9(packet_id=packet.id)
        db.session.add(packet.i9)
        db.session.flush()
    return packet.i9


def _ensure_dd(packet: HirePacket) -> HireDirectDeposit:
    if packet.direct_deposit is None:
        packet.direct_deposit = HireDirectDeposit(packet_id=packet.id)
        db.session.add(packet.direct_deposit)
        db.session.flush()
    return packet.direct_deposit


def _ensure_tax(packet: HirePacket, form_key: str) -> HireTaxElection:
    row = _tax(packet, form_key)
    if row is None:
        row = HireTaxElection(packet_id=packet.id, form_key=form_key, version=1, fields={})
        db.session.add(row)
        db.session.flush()
        packet.tax_elections.append(row)
    return row


def _form_status(packet: HirePacket) -> dict[str, str]:
    w4 = _tax(packet, "w4")
    de4 = _tax(packet, "de4")
    i9 = packet.i9
    dd = packet.direct_deposit
    notices_ok = bool(packet.notice_acks) and all(a.acknowledged_at for a in packet.notice_acks)
    return {
        "w4": "signed" if w4 and w4.signed_at else ("saved" if w4 and w4.fields else "missing"),
        "i9_section1": "signed" if i9 and i9.section1_signed_at else ("saved" if i9 and i9.attestation else "missing"),
        "i9_section2": "signed" if i9 and i9.section2_signed_at else (
            "scheduled" if packet.i9_section2_scheduled_at else "missing"
        ),
        "de4": "signed" if de4 and de4.signed_at else ("saved" if de4 and de4.fields else "missing"),
        "deposit": "signed" if dd and dd.signed_at else (
            "check" if packet.pay_by_check else ("saved" if dd and dd.bank_name else "missing")
        ),
        "notices": "signed" if notices_ok else "missing",
    }


def serialize_list_row(packet: HirePacket, *, full: bool) -> dict[str, Any]:
    person = packet.person
    due = i9_section2_due(packet.start_of_work_date)
    days = None
    if due and packet.stage not in ("void", "closed") and not (packet.i9 and packet.i9.section2_signed_at):
        days = (due - _today_la()).days
    forms = _form_status(packet)
    name = _display_name(packet)
    row = {
        "id": str(packet.id),
        "employee": name,
        "job_title": packet.job_title,
        "start_of_work_date": _iso(packet.start_of_work_date),
        "stage": packet.stage,
        "hire_type": packet.hire_type,
        "invite_email": packet.invite_email if full else None,
        "days_to_i9_section2_due": days,
        "i9_section2_due": _iso(due),
        "owner_user_id": str(packet.owner_user_id) if packet.owner_user_id else None,
        "owner": None,
        "user_id": str(packet.user_id) if packet.user_id and full else None,
        "forms": forms if full else None,
        "w4": forms["w4"] if full else None,
        "i9_section1": forms["i9_section1"] if full else None,
        "i9_section2": forms["i9_section2"] if full else None,
        "de4": forms["de4"] if full else None,
        "deposit": forms["deposit"] if full else None,
        "notices": forms["notices"] if full else None,
    }
    if not full:
        row.pop("invite_email", None)
        row.pop("user_id", None)
        row.pop("forms", None)
        row.pop("job_title", None)
        row.pop("hire_type", None)
        row.pop("days_to_i9_section2_due", None)
        row.pop("i9_section2_due", None)
        row.pop("owner_user_id", None)
        row.pop("owner", None)
        row.pop("w4", None)
        row.pop("i9_section1", None)
        row.pop("i9_section2", None)
        row.pop("de4", None)
        row.pop("deposit", None)
        row.pop("notices", None)
    return row


def _w4_fields(packet: HirePacket) -> dict[str, Any]:
    row = _tax(packet, "w4")
    return dict(row.fields or {}) if row else {}


def _de4_fields(packet: HirePacket) -> dict[str, Any]:
    row = _tax(packet, "de4")
    return dict(row.fields or {}) if row else {}


def serialize_detail(packet: HirePacket, cu: CurrentUser, *, reveal_ssn: bool = False) -> dict[str, Any]:
    full = is_hr_full(cu)
    person = packet.person
    i9 = packet.i9
    dd = packet.direct_deposit
    ssn_plain = decrypt_str(person.ssn_ciphertext) if person and full and reveal_ssn else None
    dob_plain = decrypt_str(person.dob_ciphertext) if person and full else None
    out = serialize_list_row(packet, full=full)
    out.update(
        {
            "employment_class": packet.employment_class,
            "union_status": packet.union_status,
            "union_local_name": packet.union_local_name,
            "wage_order": packet.wage_order,
            "work_state": packet.work_state,
            "drives_for_work": packet.drives_for_work,
            "requires_e_verify": packet.requires_e_verify if full else None,
            "pay_frequency": packet.pay_frequency,
            "show_rate_on_packet": packet.show_rate_on_packet,
            "pay_rate_display": packet.pay_rate_display if full else (packet.pay_rate_display if packet.show_rate_on_packet else None),
            "primary_project_id": str(packet.primary_project_id) if packet.primary_project_id else None,
            "form_pack_version_id": packet.form_pack_version_id,
            "workflow_definition_version": packet.workflow_definition_version,
            "workflow_instance_id": str(packet.workflow_instance_id) if packet.workflow_instance_id else None,
            "invited_at": _iso(packet.invited_at),
            "employee_signed_at": _iso(packet.employee_signed_at),
            "locked_at": _iso(packet.locked_at),
            "voided_at": _iso(packet.voided_at),
            "void_reason": packet.void_reason,
            "send_back_note": packet.send_back_note,
            "wizard_step": packet.wizard_step,
            "pay_by_check": packet.pay_by_check,
            "i9_section2_scheduled_at": _iso(packet.i9_section2_scheduled_at),
            "de34_filed": bool(packet.de34_filed_at),
            "de34_confirmation": packet.de34_confirmation if full else None,
            "qb_created": bool(packet.qb_created_at),
            "qb_list_id": packet.qb_list_id if full else None,
            "token_expires_at": _iso(packet.token_expires_at),
            "i9_section2_late": bool(i9.section2_late) if i9 else False,
            "payroll_gates": payroll_gates(packet) if full else None,
            "payroll_gate_labels": PAYROLL_GATE_LABELS if full else None,
            "examiner_name": (
                " ".join(
                    p for p in (
                        (cu.user.first_name if cu.user else None),
                        (cu.user.last_name if cu.user else None),
                    ) if p
                ).strip()
                or (cu.user.email if cu.user else "")
            ),
            "i9_employer_business_name": setting("i9_section2_business_name"),
            "i9_employer_address": setting("i9_section2_address"),
        }
    )
    if person and full:
        out["person"] = {
            "legal_first": person.legal_first,
            "legal_middle": person.legal_middle,
            "legal_last": person.legal_last,
            "legal_suffix": person.legal_suffix,
            "preferred_name": person.preferred_name,
            "legal_name": _legal_name(person),
            "ssn_masked": f"***-**-{person.ssn_last4}" if person.ssn_last4 else None,
            "ssn": ssn_plain,
            "dob": dob_plain,
            "email": person.email,
            "mobile": person.mobile,
            "address1": person.address1,
            "address2": person.address2,
            "city": person.city,
            "state": person.state,
            "zip": person.zip,
            "county": person.county,
            "dl_number": person.dl_number,
            "dl_state": person.dl_state,
            "last_company": person.last_company,
            "referred_by": person.referred_by,
        }
    elif person:
        out["person"] = {"preferred_name": person.preferred_name, "legal_last": person.legal_last}
    if full:
        out["w4_fields"] = {**_w4_fields(packet), "signed_at": _iso(_tax(packet, "w4").signed_at) if _tax(packet, "w4") else None}
        out["de4_fields"] = {
            **_de4_fields(packet),
            "signed_at": _iso(_tax(packet, "de4").signed_at) if _tax(packet, "de4") else None,
        }
        if i9:
            out["i9"] = {
                "attestation": i9.attestation,
                "uscis_a_number": i9.uscis_a_number,
                "i94_number": i9.i94_number,
                "foreign_passport_number": i9.foreign_passport_number,
                "foreign_passport_country": i9.foreign_passport_country,
                "work_until": _iso(i9.work_until),
                "section1_signed_at": _iso(i9.section1_signed_at),
                "first_day_of_employment": _iso(i9.first_day_of_employment),
                "additional_information": i9.additional_information,
                "examiner_name": i9.examiner_name,
                "examiner_title": i9.examiner_title,
                "employer_business_name": i9.employer_business_name,
                "employer_address": i9.employer_address,
                "section2_signed_at": _iso(i9.section2_signed_at),
                "section2_late": i9.section2_late,
                "document_list_mode": i9.document_list_mode,
                "documents": [
                    {
                        "id": str(d.id),
                        "list_kind": d.list_kind,
                        "document_title": d.document_title,
                        "issuing_authority": d.issuing_authority,
                        "document_number": d.document_number,
                        "expiration": _iso(d.expiration),
                        "expiration_na": d.expiration_na,
                        "has_copy": bool(d.copy_storage_name),
                    }
                    for d in (i9.documents or [])
                ],
            }
        if dd:
            routing = decrypt_str(dd.routing_ciphertext) if reveal_ssn else None
            account = decrypt_str(dd.account_ciphertext) if reveal_ssn else None
            out["direct_deposit"] = {
                "bank_name": dd.bank_name,
                "account_type": dd.account_type,
                "account_holder_name": dd.account_holder_name,
                "account_last4": dd.account_last4,
                "routing_last4": last4(routing) if routing else None,
                "routing": routing,
                "account": account,
                "signed_at": _iso(dd.signed_at),
                "has_voided_check": bool(dd.voided_check_storage_name),
            }
        out["emergency_contacts"] = [
            {"name": c.name, "relation": c.relation, "phone": c.phone, "sort_order": c.sort_order}
            for c in (packet.emergency_contacts or [])
        ]
        out["notice_acks"] = [
            {"notice_key": a.notice_key, "acknowledged_at": _iso(a.acknowledged_at)}
            for a in (packet.notice_acks or [])
        ]
        out["notice_catalog"] = [{"key": k, "title": t} for k, t in NOTICE_KEYS]
    return out


def serialize_public(packet: HirePacket, *, readonly: bool = False) -> dict[str, Any]:
    person = packet.person or _ensure_person(packet)
    i9 = packet.i9
    dd = packet.direct_deposit
    w4 = _w4_fields(packet)
    de4 = _de4_fields(packet)
    closed_note = None
    if packet.stage == "void":
        raise HireApiError("packet not found", 404)
    if packet.locked_at:
        return {
            "status": "closed",
            "message": "This packet is closed. Contact HR.",
        }
    signed = packet.stage in ("employee_signed", "hr_review", "i9_section2", "ready_for_payroll", "payroll_setup", "closed")
    return {
        "status": "signed" if signed else "open",
        "readonly": bool(readonly or signed),
        "company_name": setting("employer_legal_name", "US Interior Specialties"),
        "job_title": packet.job_title,
        "start_of_work_date": _iso(packet.start_of_work_date),
        "hire_type": packet.hire_type,
        "wage_order": packet.wage_order,
        "work_state": packet.work_state,
        "drives_for_work": packet.drives_for_work,
        "show_rate_on_packet": packet.show_rate_on_packet,
        "pay_rate_display": packet.pay_rate_display if packet.show_rate_on_packet else None,
        "wizard_step": packet.wizard_step,
        "send_back_note": packet.send_back_note,
        "cert_text": CERT_TEXT,
        "w4_exempt_text": W4_EXEMPT_TEXT,
        "w4_step_wording": W4_STEP_WORDING,
        "notice_catalog": [{"key": k, "title": t} for k, t in NOTICE_KEYS],
        "person": {
            "legal_first": person.legal_first,
            "legal_middle": person.legal_middle,
            "legal_last": person.legal_last,
            "legal_suffix": person.legal_suffix,
            "preferred_name": person.preferred_name,
            "ssn": decrypt_str(person.ssn_ciphertext) if person.ssn_ciphertext else "",
            "dob": decrypt_str(person.dob_ciphertext) if person.dob_ciphertext else "",
            "email": person.email or packet.invite_email,
            "mobile": person.mobile,
            "address1": person.address1,
            "address2": person.address2,
            "city": person.city,
            "state": person.state,
            "zip": person.zip,
            "county": person.county,
            "mailing_same_as_residential": person.mailing_same_as_residential,
            "mailing_address1": person.mailing_address1,
            "mailing_city": person.mailing_city,
            "mailing_state": person.mailing_state,
            "mailing_zip": person.mailing_zip,
            "dl_number": person.dl_number,
            "dl_state": person.dl_state,
            "last_company": person.last_company,
            "referred_by": person.referred_by,
        },
        "i9": {
            "attestation": i9.attestation if i9 else None,
            "uscis_a_number": i9.uscis_a_number if i9 else None,
            "i94_number": i9.i94_number if i9 else None,
            "foreign_passport_number": i9.foreign_passport_number if i9 else None,
            "foreign_passport_country": i9.foreign_passport_country if i9 else None,
            "work_until": _iso(i9.work_until) if i9 else None,
        },
        "w4": w4,
        "de4": de4,
        "direct_deposit": {
            "bank_name": dd.bank_name if dd else None,
            "routing": decrypt_str(dd.routing_ciphertext) if dd else "",
            "account": decrypt_str(dd.account_ciphertext) if dd else "",
            "account_type": dd.account_type if dd else None,
            "account_holder_name": dd.account_holder_name if dd else None,
            "pay_by_check": packet.pay_by_check,
            "has_voided_check": bool(dd.voided_check_storage_name) if dd else False,
        },
        "emergency_contacts": [
            {"name": c.name, "relation": c.relation, "phone": c.phone, "sort_order": c.sort_order}
            for c in (packet.emergency_contacts or [])
        ],
        "notice_acks": {a.notice_key: bool(a.acknowledged_at) for a in (packet.notice_acks or [])},
        "forms": _form_status(packet),
    }


def list_packets(cu: CurrentUser, args: dict[str, str]) -> dict[str, Any]:
    q = select(HirePacket).options(selectinload(HirePacket.person), selectinload(HirePacket.i9), selectinload(HirePacket.direct_deposit), selectinload(HirePacket.tax_elections), selectinload(HirePacket.notice_acks))
    stage = (args.get("stage") or "").strip()
    if stage:
        q = q.where(HirePacket.stage == stage)
    if (args.get("incomplete_i9") or "").strip() in ("1", "true"):
        q = q.where(HirePacket.stage.notin_(("void", "closed")))
    q = q.order_by(HirePacket.start_of_work_date.asc().nullslast(), HirePacket.created_at.desc())
    week = (args.get("start_week") or "").strip()
    if week:
        try:
            year_s, week_s = week.upper().split("-W")
            start = date.fromisocalendar(int(year_s), int(week_s), 1)
            end = date.fromisocalendar(int(year_s), int(week_s), 7)
            q = q.where(HirePacket.start_of_work_date >= start, HirePacket.start_of_work_date <= end)
        except ValueError:
            pass
    rows = list(db.session.scalars(q).all())
    full = is_hr_full(cu)
    owner_ids = {p.owner_user_id for p in rows if p.owner_user_id}
    owners: dict = {}
    if owner_ids:
        from ..models import User

        owners = {
            u.id: ((u.first_name or "") + " " + (u.last_name or "")).strip() or (u.email or "")
            for u in db.session.scalars(select(User).where(User.id.in_(owner_ids))).all()
        }
    items = []
    incomplete_i9 = (args.get("incomplete_i9") or "").strip() in ("1", "true")
    for p in rows:
        forms = _form_status(p)
        if incomplete_i9 and forms["i9_section1"] == "signed" and forms["i9_section2"] == "signed":
            continue
        if (args.get("missing_deposit") or "").strip() in ("1", "true"):
            if p.pay_by_check or (p.direct_deposit and p.direct_deposit.bank_name):
                continue
        row = serialize_list_row(p, full=full)
        if full:
            row["owner"] = owners.get(p.owner_user_id) if p.owner_user_id else None
        items.append(row)
    return {"items": items, "full": full}


def create_packet(data: dict[str, Any], cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    ensure_form_templates()
    ensure_settings()
    title = str(data.get("job_title") or "").strip()
    start_raw = str(data.get("start_of_work_date") or "").strip()
    email = str(data.get("invite_email") or data.get("email") or "").strip().lower()
    if not title:
        raise HireApiError("job_title is required")
    if not start_raw:
        raise HireApiError("start_of_work_date is required")
    try:
        start = date.fromisoformat(start_raw[:10])
    except ValueError as exc:
        raise HireApiError("invalid start_of_work_date") from exc
    if not email or "@" not in email:
        raise HireApiError("invite email is required")
    packet = HirePacket(
        hire_type=str(data.get("hire_type") or "new").strip() or "new",
        stage="draft",
        start_of_work_date=start,
        job_title=title[:200],
        employment_class=str(data.get("employment_class") or "hourly_nonexempt")[:40],
        union_status=str(data.get("union_status") or "nonunion")[:20],
        union_local_name=(str(data.get("union_local_name") or "").strip() or None),
        wage_order=str(data.get("wage_order") or setting("default_wage_order", "16"))[:8],
        work_state=str(data.get("work_state") or "CA")[:2],
        drives_for_work=bool(data.get("drives_for_work")),
        requires_e_verify=bool(data.get("requires_e_verify")),
        show_rate_on_packet=bool(data.get("show_rate_on_packet")),
        pay_rate_display=(str(data.get("pay_rate_display") or "").strip() or None),
        pay_frequency=str(data.get("pay_frequency") or setting("default_pay_frequency", "weekly"))[:20],
        invite_email=email[:255],
        created_by=cu.id,
        owner_user_id=cu.id,
    )
    pid = data.get("primary_project_id")
    if pid:
        try:
            packet.primary_project_id = uuid.UUID(str(pid))
        except ValueError as exc:
            raise HireApiError("invalid primary_project_id") from exc
    db.session.add(packet)
    db.session.flush()
    person = HirePerson(packet_id=packet.id, email=email)
    db.session.add(person)
    _audit(cu=cu, packet=packet, action="create", message=f"Created hire packet for {email}")
    db.session.commit()
    return get_packet(packet.id)


def patch_packet(packet: HirePacket, data: dict[str, Any], cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    if packet.stage == "void":
        raise HireApiError("voided packet cannot be edited", 409)
    if packet.locked_at:
        raise HireApiError("locked packet cannot be edited", 409)
    frozen_after_start = packet.wizard_step >= 3 and packet.stage not in ("draft", "invite_sent")
    allowed = {
        "job_title",
        "hire_type",
        "employment_class",
        "union_status",
        "union_local_name",
        "wage_order",
        "work_state",
        "drives_for_work",
        "requires_e_verify",
        "show_rate_on_packet",
        "pay_rate_display",
        "pay_frequency",
        "invite_email",
        "owner_user_id",
        "pay_by_check",
        "send_back_note",
        "i9_section2_scheduled_at",
    }
    if not frozen_after_start or packet.stage == "draft":
        allowed.add("start_of_work_date")
        allowed.add("primary_project_id")
    for key in allowed:
        if key not in data:
            continue
        val = data[key]
        if key == "start_of_work_date":
            packet.start_of_work_date = date.fromisoformat(str(val)[:10]) if val else None
        elif key == "i9_section2_scheduled_at":
            packet.i9_section2_scheduled_at = date.fromisoformat(str(val)[:10]) if val else None
        elif key in ("drives_for_work", "requires_e_verify", "show_rate_on_packet", "pay_by_check"):
            setattr(packet, key, bool(val))
        elif key == "owner_user_id":
            packet.owner_user_id = uuid.UUID(str(val)) if val else None
        elif key == "primary_project_id":
            packet.primary_project_id = uuid.UUID(str(val)) if val else None
        elif key == "invite_email" and val:
            packet.invite_email = str(val).strip().lower()[:255]
        else:
            setattr(packet, key, None if val is None else str(val)[:200])
    _audit(cu=cu, packet=packet, action="patch", message="Updated hire packet")
    db.session.commit()
    return get_packet(packet.id)


def _token_expiry(packet: HirePacket) -> datetime:
    invited = packet.invited_at or _utcnow()
    from_invite = invited + timedelta(days=30)
    start = packet.start_of_work_date or _today_la()
    from_start = datetime.combine(start + timedelta(days=14), datetime.min.time(), tzinfo=LA).astimezone(timezone.utc)
    return max(from_invite, from_start)


def _set_stage(packet: HirePacket, stage: str, cu: CurrentUser | None = None) -> None:
    packet.stage = stage
    if packet.workflow_instance_id:
        try:
            wf.complete_subject_step(
                process_key=PROCESS_NEW_HIRE,
                subject_type=SUBJECT_HIRE,
                subject_id=packet.id,
                step_key=stage if stage != "void" else "void",
                cu=cu,
            )
        except Exception:
            current_app.logger.exception("hire workflow step %s", stage)


def _public_origin() -> str:
    from ._notifications import public_app_origin

    return public_app_origin()


def _send_invite_email(packet: HirePacket, raw_token: str) -> None:
    from ._notifications import send_html_notification_email

    url = f"{_public_origin()}/public/hire/{raw_token}"
    from_addr = setting("hire_mail_from", "hr@gousis.com")
    reply = setting("hire_mail_reply_to", from_addr)
    company = setting("employer_legal_name", "US Interior Specialties")
    html = render_template(
        "email/hire_invite.html",
        company=company,
        job_title=packet.job_title,
        start_of_work_date=packet.start_of_work_date,
        url=url,
    )
    text = render_template(
        "email/hire_invite.txt",
        company=company,
        job_title=packet.job_title,
        start_of_work_date=packet.start_of_work_date,
        url=url,
    )
    send_html_notification_email(
        to=packet.invite_email or "",
        subject=f"{company} new-hire packet — {packet.job_title}",
        body=text,
        html_body=html,
        from_addr=from_addr,
        reply_to=reply,
        bcc=from_addr,
        from_name=company,
    )


def invite_packet(packet: HirePacket, cu: CurrentUser, *, resend: bool = False) -> dict[str, Any]:
    require_hr_full(cu)
    if packet.stage == "void":
        raise HireApiError("cannot invite a voided packet", 409)
    if not packet.job_title or not packet.start_of_work_date:
        raise HireApiError("job title and start date are required before invite")
    if not packet.invite_email:
        raise HireApiError("invite email is required")
    templates = default_template_ids()
    raw = secrets.token_urlsafe(32)
    packet.public_token_hash = hash_token(raw)
    packet.invited_at = packet.invited_at or _utcnow()
    packet.token_expires_at = _token_expiry(packet)
    packet.form_pack_version_id = packet.form_pack_version_id or FORM_PACK_VERSION
    packet.form_template_ids = packet.form_template_ids or templates
    if packet.workflow_instance_id is None:
        inst = wf.ensure_instance(
            process_key=PROCESS_NEW_HIRE,
            subject_type=SUBJECT_HIRE,
            subject_id=packet.id,
            cu=cu,
        )
        packet.workflow_instance_id = inst.id
        packet.workflow_definition_version = inst.definition_version
        try:
            wf.complete_subject_step(
                process_key=PROCESS_NEW_HIRE,
                subject_type=SUBJECT_HIRE,
                subject_id=packet.id,
                step_key="draft",
                cu=cu,
            )
        except Exception:
            current_app.logger.exception("hire workflow draft complete")
    packet.stage = "invite_sent"
    try:
        wf.complete_subject_step(
            process_key=PROCESS_NEW_HIRE,
            subject_type=SUBJECT_HIRE,
            subject_id=packet.id,
            step_key="invite_sent",
            cu=cu,
        )
    except Exception:
        pass
    _audit(cu=cu, packet=packet, action="invite" if not resend else "resend", message="Sent hire invite")
    db.session.commit()
    try:
        celery = None
        try:
            from ..celery_app import celery as celery_app

            celery = celery_app
        except Exception:
            celery = None
        queued = False
        if celery is not None:
            celery.send_task("hire.send_invite", kwargs={"packet_id": str(packet.id), "raw_token": raw})
            queued = True
        if not queued:
            _send_invite_email(packet, raw)
    except Exception:
        current_app.logger.exception("hire invite email")
        try:
            _send_invite_email(packet, raw)
        except Exception:
            current_app.logger.exception("hire invite email fallback")
    return {
        "ok": True,
        "id": str(packet.id),
        "stage": packet.stage,
        "invite_url": f"{_public_origin()}/public/hire/{raw}",
        "token_expires_at": _iso(packet.token_expires_at),
        "workflow_definition_version": packet.workflow_definition_version,
        "form_pack_version_id": packet.form_pack_version_id,
    }


def void_packet(packet: HirePacket, reason: str, cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    if not (reason or "").strip():
        raise HireApiError("void reason is required")
    packet.stage = "void"
    packet.voided_at = _utcnow()
    packet.void_reason = reason.strip()[:2000]
    packet.public_token_hash = None
    packet.token_expires_at = _utcnow()
    _audit(cu=cu, packet=packet, action="void", message="Voided hire packet")
    db.session.commit()
    return packet


def packet_by_token(token: str) -> HirePacket:
    raw = (token or "").strip()
    if len(raw) < 16:
        raise HireApiError("packet not found", 404)
    hashed = hash_token(raw)
    row = db.session.scalars(_packet_query().where(HirePacket.public_token_hash == hashed)).first()
    if row is None:
        raise HireApiError("packet not found", 404)
    if row.stage == "void":
        raise HireApiError("packet not found", 404)
    if row.locked_at:
        raise HireApiError("This packet is closed. Contact HR.", 404)
    if row.token_expires_at and row.token_expires_at < _utcnow():
        raise HireApiError("packet not found", 404)
    return row


def rate_limit_public(token: str) -> None:
    import time

    ip = _client_ip() or "x"
    key = f"{ip}:{token[:12]}"
    now = time.time()
    bucket = [t for t in _RATE.get(key, []) if now - t < 60]
    if len(bucket) >= 40:
        raise HireApiError("too many requests", 429)
    bucket.append(now)
    _RATE[key] = bucket


def public_get(token: str) -> dict[str, Any]:
    require_public_https()
    packet = packet_by_token(token)
    signed = packet.employee_signed_at is not None
    return serialize_public(packet, readonly=signed)


def require_public_https() -> None:
    import os

    if os.environ.get("FLASK_ENV", "").strip().lower() == "production" and not request.is_secure:
        raise HireApiError("HTTPS required", 403)


def _parse_date(val: Any) -> date | None:
    if not val:
        return None
    return date.fromisoformat(str(val)[:10])


def _apply_you(packet: HirePacket, data: dict[str, Any]) -> None:
    person = _ensure_person(packet)
    for field in (
        "legal_first",
        "legal_middle",
        "legal_last",
        "legal_suffix",
        "preferred_name",
        "email",
        "mobile",
        "address1",
        "address2",
        "city",
        "state",
        "zip",
        "county",
        "dl_number",
        "dl_state",
        "last_company",
        "referred_by",
    ):
        if field in data:
            val = data.get(field)
            setattr(person, field, None if val in (None, "") else str(val)[:255])
    if "mailing_same_as_residential" in data:
        person.mailing_same_as_residential = bool(data.get("mailing_same_as_residential"))
    for field in ("mailing_address1", "mailing_city", "mailing_state", "mailing_zip"):
        if field in data:
            val = data.get(field)
            setattr(person, field, None if val in (None, "") else str(val)[:255])
    if person.mailing_same_as_residential:
        person.mailing_address1 = person.address1
        person.mailing_city = person.city
        person.mailing_state = person.state
        person.mailing_zip = person.zip
    if "ssn" in data and data.get("ssn"):
        ssn = normalize_ssn(str(data.get("ssn")))
        person.ssn_ciphertext = encrypt_str(ssn)
        person.ssn_last4 = last4(ssn)
    if "dob" in data and data.get("dob"):
        dob = str(data.get("dob"))[:10]
        person.dob_ciphertext = encrypt_str(dob)


def _apply_eligibility(packet: HirePacket, data: dict[str, Any]) -> None:
    i9 = _ensure_i9(packet)
    att = str(data.get("attestation") or "").strip()
    allowed = {
        "us_citizen",
        "noncitizen_national",
        "lawful_permanent_resident",
        "alien_authorized_to_work",
    }
    if att and att not in allowed:
        raise HireApiError("invalid I-9 attestation")
    if att:
        i9.attestation = att
    i9.uscis_a_number = (str(data.get("uscis_a_number") or "").strip() or None)
    i9.i94_number = (str(data.get("i94_number") or "").strip() or None)
    i9.foreign_passport_number = (str(data.get("foreign_passport_number") or "").strip() or None)
    i9.foreign_passport_country = (str(data.get("foreign_passport_country") or "").strip() or None)
    i9.work_until = _parse_date(data.get("work_until"))


def _zero_w4_steps(fields: dict[str, Any]) -> dict[str, Any]:
    fields["step2"] = False
    fields["step3"] = 0
    fields["step4a"] = 0
    fields["step4b"] = 0
    fields["step4c"] = 0
    fields["other_income"] = 0
    fields["deductions"] = 0
    fields["extra_withholding"] = 0
    return fields


def _apply_w4(packet: HirePacket, data: dict[str, Any]) -> None:
    row = _ensure_tax(packet, "w4")
    fields = dict(row.fields or {})
    for key in ("filing_status", "step2", "step3", "step4a", "step4b", "step4c", "exempt", "other_income", "deductions", "extra_withholding"):
        if key in data:
            fields[key] = data[key]
    if fields.get("exempt"):
        fields = _zero_w4_steps(fields)
    row.fields = fields


def _apply_de4(packet: HirePacket, data: dict[str, Any]) -> None:
    row = _ensure_tax(packet, "de4")
    fields = dict(row.fields or {})
    for key in ("filing_status", "regular_allowances", "additional_allowances", "extra_withholding", "exempt"):
        if key in data:
            fields[key] = data[key]
    row.fields = fields


def _apply_deposit(packet: HirePacket, data: dict[str, Any]) -> None:
    if data.get("pay_by_check"):
        packet.pay_by_check = True
        return
    packet.pay_by_check = False
    dd = _ensure_dd(packet)
    if "bank_name" in data:
        dd.bank_name = str(data.get("bank_name") or "")[:200]
    if "account_type" in data:
        dd.account_type = str(data.get("account_type") or "")[:20]
    if "account_holder_name" in data:
        dd.account_holder_name = str(data.get("account_holder_name") or "")[:200]
    if data.get("routing"):
        routing = normalize_routing(str(data.get("routing")))
        dd.routing_ciphertext = encrypt_str(routing)
    if data.get("account"):
        acct = str(data.get("account")).strip()
        dd.account_ciphertext = encrypt_str(acct)
        dd.account_last4 = last4(acct)


def _apply_emergency(packet: HirePacket, data: dict[str, Any]) -> None:
    contacts = data.get("emergency_contacts") or []
    if isinstance(contacts, list) and contacts:
        for old in list(packet.emergency_contacts or []):
            db.session.delete(old)
        db.session.flush()
        packet.emergency_contacts = []
        for i, c in enumerate(contacts[:2], start=1):
            row = HireEmergencyContact(
                packet_id=packet.id,
                sort_order=i,
                name=str((c or {}).get("name") or "")[:200],
                relation=str((c or {}).get("relation") or "")[:80],
                phone=str((c or {}).get("phone") or "")[:50],
            )
            db.session.add(row)
    acks = data.get("notice_acks") or {}
    if isinstance(acks, dict):
        for key, title in NOTICE_KEYS:
            wanted = bool(acks.get(key))
            row = next((a for a in (packet.notice_acks or []) if a.notice_key == key), None)
            if row is None:
                row = HireNoticeAck(packet_id=packet.id, notice_key=key)
                db.session.add(row)
                packet.notice_acks.append(row)
            if wanted and not row.acknowledged_at:
                row.acknowledged_at = _utcnow()
            if not wanted:
                row.acknowledged_at = None


def public_patch(token: str, data: dict[str, Any]) -> dict[str, Any]:
    require_public_https()
    rate_limit_public(token)
    for bad in _PUBLIC_FORBIDDEN:
        if bad in data:
            raise HireApiError("field is not allowed on the public form", 400)
    nested = data.get("step_payload") if isinstance(data.get("step_payload"), dict) else data
    for bad in _PUBLIC_FORBIDDEN:
        if bad in nested:
            raise HireApiError("field is not allowed on the public form", 400)
    packet = packet_by_token(token)
    if packet.employee_signed_at:
        raise HireApiError("packet already submitted", 409)
    step = int(data.get("step") or nested.get("step") or packet.wizard_step or 1)
    payload = nested.get("data") if isinstance(nested.get("data"), dict) else nested
    if step >= 2:
        _apply_you(packet, payload.get("person") if isinstance(payload.get("person"), dict) else payload)
    if step >= 3:
        _apply_eligibility(packet, payload.get("i9") if isinstance(payload.get("i9"), dict) else payload)
    if step >= 4:
        _apply_w4(packet, payload.get("w4") if isinstance(payload.get("w4"), dict) else payload)
    if step >= 5:
        _apply_de4(packet, payload.get("de4") if isinstance(payload.get("de4"), dict) else payload)
    if step >= 6:
        _apply_deposit(packet, payload.get("direct_deposit") if isinstance(payload.get("direct_deposit"), dict) else payload)
    if step >= 7:
        _apply_emergency(packet, payload)
    packet.wizard_step = max(packet.wizard_step, min(step, 8))
    if packet.stage == "invite_sent":
        packet.stage = "employee_in_progress"
        try:
            wf.complete_subject_step(
                process_key=PROCESS_NEW_HIRE,
                subject_type=SUBJECT_HIRE,
                subject_id=packet.id,
                step_key="employee_in_progress",
            )
        except Exception:
            pass
    _rebuild_drafts(packet)
    _audit(cu=None, packet=packet, action="save", message=f"Employee saved step {step}")
    db.session.commit()
    return serialize_public(packet)


def _pdf_ctx(packet: HirePacket) -> dict[str, Any]:
    person = packet.person
    i9 = packet.i9
    dd = packet.direct_deposit
    w4 = _w4_fields(packet)
    de4 = _de4_fields(packet)
    ssn = decrypt_str(person.ssn_ciphertext) if person else None
    dob = decrypt_str(person.dob_ciphertext) if person else None
    routing = decrypt_str(dd.routing_ciphertext) if dd else None
    docs = []
    if i9:
        docs = [f"{d.list_kind}: {d.document_title or ''} {d.document_number or ''}" for d in (i9.documents or [])]
    addr = " ".join(p for p in ((person.address1 if person else None), (person.city if person else None), (person.state if person else None), (person.zip if person else None)) if p)
    return {
        "legal_name": _legal_name(person),
        "legal_first": person.legal_first if person else "",
        "legal_middle": person.legal_middle if person else "",
        "legal_last": person.legal_last if person else "",
        "address": addr,
        "ssn": ssn or "",
        "ssn_last4": person.ssn_last4 if person else "",
        "dob": dob or "",
        "email": person.email if person else "",
        "mobile": person.mobile if person else "",
        "filing_status": w4.get("filing_status"),
        "step2": w4.get("step2"),
        "step3": w4.get("step3"),
        "step4a": w4.get("step4a") or w4.get("other_income"),
        "step4b": w4.get("step4b") or w4.get("deductions"),
        "step4c": w4.get("step4c") or w4.get("extra_withholding"),
        "exempt": w4.get("exempt"),
        "signed_at": _iso(_tax(packet, "w4").signed_at) if _tax(packet, "w4") else None,
        "attestation": i9.attestation if i9 else "",
        "uscis_a_number": i9.uscis_a_number if i9 else "",
        "i94_number": i9.i94_number if i9 else "",
        "foreign_passport_number": i9.foreign_passport_number if i9 else "",
        "work_until": _iso(i9.work_until) if i9 else "",
        "section1_signed_at": _iso(i9.section1_signed_at) if i9 else None,
        "first_day": _iso((i9.first_day_of_employment if i9 else None) or packet.start_of_work_date),
        "document_list_mode": i9.document_list_mode if i9 else "",
        "documents_summary": "; ".join(docs),
        "examiner_name": i9.examiner_name if i9 else "",
        "examiner_title": i9.examiner_title if i9 else "",
        "employer_business_name": i9.employer_business_name if i9 else "",
        "employer_address": i9.employer_address if i9 else "",
        "section2_signed_at": _iso(i9.section2_signed_at) if i9 else None,
        "section2_late": bool(i9.section2_late) if i9 else False,
        "regular_allowances": de4.get("regular_allowances"),
        "additional_allowances": de4.get("additional_allowances"),
        "extra_withholding": de4.get("extra_withholding"),
        "bank_name": dd.bank_name if dd else "",
        "routing": routing or "",
        "account_last4": dd.account_last4 if dd else "",
        "account_type": dd.account_type if dd else "",
        "account_holder_name": dd.account_holder_name if dd else "",
        "acks": [
            {"key": a.notice_key, "title": dict(NOTICE_KEYS).get(a.notice_key, a.notice_key), "acknowledged_at": _iso(a.acknowledged_at)}
            for a in (packet.notice_acks or [])
        ],
        "start_of_work_date": _iso(packet.start_of_work_date),
        "employer_legal_name": setting("employer_legal_name"),
        "edd_masked": ("****" + (last4(setting("edd_account_number")) or "")) if setting("edd_account_number") else "",
        "fein_masked": ("****" + (last4(setting("employer_fein")) or "")) if setting("employer_fein") else "",
        "job_title": packet.job_title,
    }


def _store_artifact(packet: HirePacket, key: str, payload: bytes, *, draft: bool, filename: str) -> HireArtifact:
    name = f"{packet.id}/{key}{'-draft' if draft else ''}.pdf"
    save_upload(UploadCategory.HR_HIRE, name, io.BytesIO(payload))
    row = next((a for a in (packet.artifacts or []) if a.artifact_key == key and a.is_draft == draft), None)
    if row is None:
        row = HireArtifact(packet_id=packet.id, artifact_key=key)
        db.session.add(row)
        packet.artifacts.append(row)
    row.is_draft = draft
    row.storage_name = name
    row.sha256 = sha256_bytes(payload)
    row.original_filename = filename
    row.mime_type = "application/pdf"
    row.file_size_bytes = len(payload)
    db.session.flush()
    return row


def _rebuild_drafts(packet: HirePacket) -> None:
    ctx = _pdf_ctx(packet)
    _store_artifact(packet, "w4", render_w4(ctx, draft=True), draft=True, filename="w4-draft.pdf")
    _store_artifact(packet, "i9", render_i9(ctx, draft=True), draft=True, filename="i9-draft.pdf")
    _store_artifact(packet, "de4", render_de4(ctx, draft=True), draft=True, filename="de4-draft.pdf")
    _store_artifact(packet, "dd_auth", render_dd_auth(ctx, draft=True), draft=True, filename="dd-draft.pdf")
    _store_artifact(packet, "notices", render_notices(ctx, draft=True), draft=True, filename="notices-draft.pdf")


def preview_pdf(packet: HirePacket, form_key: str, *, draft: bool = True) -> tuple[bytes, str]:
    ctx = _pdf_ctx(packet)
    key = (form_key or "").strip().lower()
    sig = None
    if not draft:
        row = next((s for s in (packet.signatures or []) if s.artifact_key == key), None)
        sig = row.signature_png if row else None
    if key in ("w4", "w4_2026"):
        return render_w4(ctx, draft=draft, signature_png=sig), "w4.pdf"
    if key in ("i9", "i9_01-20-25"):
        return render_i9(ctx, draft=draft, signature_png=sig), "i9.pdf"
    if key in ("de4", "de4_current"):
        return render_de4(ctx, draft=draft, signature_png=sig), "de4.pdf"
    if key in ("dd", "dd_auth"):
        return render_dd_auth(ctx, draft=draft, signature_png=sig), "direct-deposit.pdf"
    if key in ("notices", "ack"):
        return render_notices(ctx, draft=draft, signature_png=sig), "notices.pdf"
    notice_titles = dict(NOTICE_KEYS)
    if key in notice_titles:
        return render_notice_placeholder(notice_titles[key]), f"{key}.pdf"
    if key in ("de34",):
        ctx_full = dict(ctx)
        person = packet.person
        ctx_full["ssn"] = decrypt_str(person.ssn_ciphertext) if person else ""
        return render_de34(ctx_full), "de34.pdf"
    raise HireApiError("unknown form", 404)


def _required_employee_ready(packet: HirePacket) -> None:
    person = packet.person
    if not person or not person.legal_first or not person.legal_last:
        raise HireApiError("legal first and last name are required")
    if not person.ssn_ciphertext:
        raise HireApiError("SSN is required")
    if not person.dob_ciphertext:
        raise HireApiError("date of birth is required")
    i9 = packet.i9
    if not i9 or not i9.attestation:
        raise HireApiError("I-9 Section 1 attestation is required")
    w4 = _tax(packet, "w4")
    if not w4 or not (w4.fields or {}).get("filing_status"):
        if not (w4 and (w4.fields or {}).get("exempt")):
            raise HireApiError("W-4 filing status is required")
    de4 = _tax(packet, "de4")
    if not de4 or not (de4.fields or {}):
        raise HireApiError("DE-4 elections are required")
    if not packet.pay_by_check:
        dd = packet.direct_deposit
        if not dd or not dd.routing_ciphertext or not dd.account_ciphertext:
            raise HireApiError("direct deposit or pay-by-check is required")
    acks = {a.notice_key: a.acknowledged_at for a in (packet.notice_acks or [])}
    missing = [k for k, _t in NOTICE_KEYS if not acks.get(k)]
    if missing:
        raise HireApiError("all California notices must be acknowledged")
    contacts = [c for c in (packet.emergency_contacts or []) if c.name and c.phone]
    if len(contacts) < 2:
        raise HireApiError("two emergency contacts are required")


def public_sign(token: str, data: dict[str, Any]) -> dict[str, Any]:
    require_public_https()
    rate_limit_public(token)
    packet = packet_by_token(token)
    if packet.employee_signed_at:
        raise HireApiError("packet already submitted", 409)
    _required_employee_ready(packet)
    checks = data.get("certifications") or {}
    needed = ("w4", "i9", "de4", "dd_auth", "notices")
    if packet.pay_by_check:
        needed = ("w4", "i9", "de4", "notices")
    for key in needed:
        if not checks.get(key):
            raise HireApiError("each form certification must be checked before signing", 400)
    typed = str(data.get("typed_legal_name") or "").strip()
    legal = _legal_name(packet.person)
    if typed.casefold() != legal.casefold():
        raise HireApiError("typed name must match legal name on the packet", 400)
    png = str(data.get("signature_png") or "").strip()
    if not png:
        raise HireApiError("drawn signature is required", 400)
    now = _utcnow()
    ip = _client_ip()
    ua = (request.user_agent.string or "")[:500]
    ctx = _pdf_ctx(packet)
    frozen: dict[str, bytes] = {
        "w4": render_w4(ctx, draft=False, signature_png=png),
        "i9": render_i9(ctx, draft=False, signature_png=png),
        "de4": render_de4(ctx, draft=False, signature_png=png),
        "notices": render_notices(ctx, draft=False, signature_png=png),
    }
    if not packet.pay_by_check:
        frozen["dd_auth"] = render_dd_auth(ctx, draft=False, signature_png=png)
    templates = packet.form_template_ids or {}
    for key, payload in frozen.items():
        art = _store_artifact(packet, key, payload, draft=False, filename=f"{key}-signed.pdf")
        tid = templates.get({"w4": W4_KEY, "i9": I9_KEY, "de4": DE4_KEY, "dd_auth": DD_AUTH_KEY}.get(key, key))
        sig = HireSignature(
            packet_id=packet.id,
            artifact_key=key,
            typed_legal_name=typed,
            signature_png=png,
            signed_at=now,
            timezone_display="America/Los_Angeles",
            source_ip=ip,
            user_agent=ua,
            form_template_id=uuid.UUID(str(tid)) if tid else None,
            pdf_sha256=art.sha256,
            certification_checked=True,
        )
        db.session.add(sig)
    w4 = _ensure_tax(packet, "w4")
    w4.signed_at = now
    de4 = _ensure_tax(packet, "de4")
    de4.signed_at = now
    i9 = _ensure_i9(packet)
    i9.section1_signed_at = now
    if packet.direct_deposit:
        packet.direct_deposit.signed_at = now
    packet.employee_signed_at = now
    packet.stage = "employee_signed"
    try:
        wf.complete_subject_step(
            process_key=PROCESS_NEW_HIRE,
            subject_type=SUBJECT_HIRE,
            subject_id=packet.id,
            step_key="employee_signed",
        )
        wf.complete_subject_step(
            process_key=PROCESS_NEW_HIRE,
            subject_type=SUBJECT_HIRE,
            subject_id=packet.id,
            step_key="hr_review",
        )
        packet.stage = "hr_review"
    except Exception:
        pass
    _audit(cu=None, packet=packet, action="sign", message="Employee signed hire packet")
    db.session.commit()
    return serialize_public(packet, readonly=True)


def send_back(packet: HirePacket, note: str, cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    packet.send_back_note = (note or "").strip()[:2000]
    packet.employee_signed_at = None
    packet.stage = "employee_in_progress"
    for sig in list(packet.signatures or []):
        db.session.delete(sig)
    for art in list(packet.artifacts or []):
        if not art.is_draft:
            db.session.delete(art)
    w4 = _tax(packet, "w4")
    if w4:
        w4.signed_at = None
    de4 = _tax(packet, "de4")
    if de4:
        de4.signed_at = None
    if packet.i9:
        packet.i9.section1_signed_at = None
    if packet.direct_deposit:
        packet.direct_deposit.signed_at = None
    _audit(cu=cu, packet=packet, action="send_back", message="Returned packet to employee")
    db.session.commit()
    return get_packet(packet.id)


def lock_packet(packet: HirePacket, cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    packet.stage = "closed"
    packet.locked_at = _utcnow()
    packet.public_token_hash = None
    _audit(cu=cu, packet=packet, action="lock", message="Locked hire packet")
    db.session.commit()
    return get_packet(packet.id)


def reveal_ssn(packet: HirePacket, cu: CurrentUser) -> dict[str, Any]:
    require_hr_full(cu)
    person = packet.person
    if person is None or not person.ssn_ciphertext:
        raise HireApiError("no SSN on file", 404)
    _audit(cu=cu, packet=packet, action="ssn_view", message="Revealed SSN")
    db.session.commit()
    return {
        "ssn": decrypt_str(person.ssn_ciphertext),
        "dob": decrypt_str(person.dob_ciphertext) if person.dob_ciphertext else None,
    }


def save_section2(packet: HirePacket, data: dict[str, Any], cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    i9 = _ensure_i9(packet)
    if not i9.section1_signed_at:
        raise HireApiError("I-9 Section 1 must be signed first", 409)
    start = _parse_date(data.get("first_day_of_employment")) or packet.start_of_work_date
    if not start:
        raise HireApiError("first day of employment is required")
    mode = str(data.get("document_list_mode") or data.get("mode") or "").upper()
    docs = data.get("documents") or []
    lists = {str(d.get("list_kind") or "").upper() for d in docs}
    if mode == "A" or "A" in lists:
        if lists & {"B", "C"}:
            raise HireApiError("List A cannot be combined with List B or List C")
        mode = "A"
    elif lists == {"B", "C"} or mode == "BC":
        mode = "BC"
        if "B" not in lists or "C" not in lists:
            raise HireApiError("List B and List C are both required")
    else:
        raise HireApiError("select List A or List B + List C")
    i9.document_list_mode = mode
    i9.first_day_of_employment = start
    i9.additional_information = str(data.get("additional_information") or "")[:2000] or None
    i9.examiner_user_id = cu.id
    i9.examiner_title = str(data.get("examiner_title") or "")[:120] or None
    first = (cu.user.first_name if cu.user else "") or ""
    last = (cu.user.last_name if cu.user else "") or ""
    fallback = f"{first} {last}".strip()
    if not fallback and cu.user is not None:
        fallback = cu.user.email or ""
    i9.examiner_name = str(data.get("examiner_name") or fallback)[:200]
    i9.employer_business_name = str(data.get("employer_business_name") or setting("i9_section2_business_name"))[:200]
    i9.employer_address = str(data.get("employer_address") or setting("i9_section2_address"))[:500]
    due = i9_section2_due(start)
    i9.section2_late = bool(due and _today_la() > due)
    for old in list(i9.documents or []):
        db.session.delete(old)
    db.session.flush()
    for d in docs:
        row = HireI9Document(
            i9_id=i9.id,
            list_kind=str(d.get("list_kind") or "").upper()[:1],
            document_title=str(d.get("document_title") or "")[:200] or None,
            issuing_authority=str(d.get("issuing_authority") or "")[:200] or None,
            document_number=str(d.get("document_number") or "")[:80] or None,
            expiration=_parse_date(d.get("expiration")),
            expiration_na=bool(d.get("expiration_na")),
            preset_key=str(d.get("preset_key") or "")[:80] or None,
        )
        db.session.add(row)
    if data.get("sign"):
        png = str(data.get("signature_png") or "").strip()
        if not png:
            raise HireApiError("examiner signature is required to complete Section 2")
        i9.section2_signed_at = _utcnow()
        ctx = _pdf_ctx(packet)
        payload = render_i9(ctx, draft=False, signature_png=png)
        _store_artifact(packet, "i9", payload, draft=False, filename="i9-signed.pdf")
        packet.stage = "ready_for_payroll"
        try:
            wf.complete_subject_step(
                process_key=PROCESS_NEW_HIRE,
                subject_type=SUBJECT_HIRE,
                subject_id=packet.id,
                step_key="i9_section2",
                cu=cu,
            )
            wf.complete_subject_step(
                process_key=PROCESS_NEW_HIRE,
                subject_type=SUBJECT_HIRE,
                subject_id=packet.id,
                step_key="ready_for_payroll",
                cu=cu,
            )
        except Exception:
            pass
        _audit(cu=cu, packet=packet, action="i9_section2", message="I-9 Section 2 signed")
    else:
        packet.stage = "i9_section2"
        _audit(cu=cu, packet=packet, action="i9_section2", message="I-9 Section 2 saved")
    db.session.commit()
    return get_packet(packet.id)


def save_i9_copy(packet: HirePacket, file_storage, list_kind: str, cu: CurrentUser) -> dict[str, Any]:
    require_hr_full(cu)
    i9 = _ensure_i9(packet)
    kind = (list_kind or "A").upper()[:1]
    ext = (file_storage.filename or "copy").rsplit(".", 1)[-1][:8]
    name = f"{packet.id}/i9/{kind}-{uuid.uuid4().hex}.{ext}"
    save_upload(UploadCategory.HR_HIRE, name, file_storage)
    row = HireI9Document(
        i9_id=i9.id,
        list_kind=kind,
        copy_storage_name=name,
        original_filename=(file_storage.filename or "copy")[:500],
        mime_type=getattr(file_storage, "mimetype", None),
    )
    db.session.add(row)
    _audit(cu=cu, packet=packet, action="i9_copy", message="Uploaded I-9 document copy")
    db.session.commit()
    return {"ok": True, "id": str(row.id)}


def save_voided_check(token: str, file_storage) -> dict[str, Any]:
    require_public_https()
    rate_limit_public(token)
    packet = packet_by_token(token)
    if packet.employee_signed_at:
        raise HireApiError("packet already submitted", 409)
    dd = _ensure_dd(packet)
    ext = (file_storage.filename or "check").rsplit(".", 1)[-1][:8]
    name = f"{packet.id}/dd/voided-{uuid.uuid4().hex}.{ext}"
    save_upload(UploadCategory.HR_HIRE, name, file_storage)
    dd.voided_check_storage_name = name
    dd.voided_check_filename = (file_storage.filename or "voided-check")[:500]
    _audit(cu=None, packet=packet, action="voided_check", message="Uploaded voided check")
    db.session.commit()
    return {"ok": True, "filename": dd.voided_check_filename}


def _match_user(packet: HirePacket) -> User | None:
    person = packet.person
    email = ((person.email if person else None) or packet.invite_email or "").strip().lower()
    if email:
        u = db.session.scalar(select(User).where(func.lower(User.email) == email))
        if u is not None:
            return u
    if person and person.legal_first and person.legal_last:
        matches = list(
            db.session.scalars(
                select(User).where(
                    func.lower(User.first_name) == person.legal_first.strip().lower(),
                    func.lower(User.last_name) == person.legal_last.strip().lower(),
                )
            ).all()
        )
        if len(matches) > 1:
            raise HireApiError(
                "multiple users match this legal name; link by unique email",
                409,
                extra={
                    "candidates": [
                        {
                            "id": str(u.id),
                            "email": u.email,
                            "name": " ".join(p for p in (u.first_name, u.last_name) if p).strip(),
                        }
                        for u in matches
                    ]
                },
            )
        if len(matches) == 1:
            return matches[0]
    return None


def link_user(packet: HirePacket, cu: CurrentUser) -> dict[str, Any]:
    require_hr_full(cu)
    if packet.user_id:
        user = db.session.get(User, packet.user_id)
        _ensure_time_profile(packet, user)
        db.session.commit()
        return {"ok": True, "user_id": str(packet.user_id), "created": False}
    existing = _match_user(packet)
    created = False
    if existing is None:
        person = packet.person
        email = ((person.email if person else None) or packet.invite_email or "").strip().lower()
        if not email:
            raise HireApiError("email is required to create a user")
        preferred = (person.preferred_name if person else None) or (person.legal_first if person else None)
        existing = User(
            email=email[:255],
            first_name=(preferred or "")[:120],
            last_name=(person.legal_last if person else "")[:120],
            phone=(person.mobile if person else None),
            is_active=True,
        )
        db.session.add(existing)
        db.session.flush()
        created = True
    packet.user_id = existing.id
    _ensure_time_profile(packet, existing)
    if packet.stage in ("hr_review", "i9_section2", "employee_signed"):
        if packet.i9 and packet.i9.section2_signed_at:
            packet.stage = "ready_for_payroll"
    _audit(cu=cu, packet=packet, action="link_user", message="Linked User" + (" (created)" if created else ""))
    db.session.commit()
    return {"ok": True, "user_id": str(existing.id), "created": created}


def _ensure_time_profile(packet: HirePacket, user: User | None) -> EmployeeTimeProfile | None:
    if user is None:
        return None
    profile = db.session.scalar(select(EmployeeTimeProfile).where(EmployeeTimeProfile.user_id == user.id))
    eligible = bool(packet.start_of_work_date and _today_la() >= packet.start_of_work_date)
    if profile is None:
        profile = EmployeeTimeProfile(
            user_id=user.id,
            classification=packet.job_title,
            union_local=packet.union_local_name,
            hire_date=packet.start_of_work_date,
            is_clock_eligible=eligible,
        )
        db.session.add(profile)
    else:
        if packet.start_of_work_date:
            profile.hire_date = packet.start_of_work_date
        if packet.job_title:
            profile.classification = packet.job_title
        profile.is_clock_eligible = eligible
    db.session.flush()
    return profile


def send_login(packet: HirePacket, cu: CurrentUser) -> dict[str, Any]:
    require_hr_full(cu)
    if packet.user_id is None:
        link_user(packet, cu)
        packet = get_packet(packet.id)
    user = db.session.get(User, packet.user_id)
    if user is None or not user.email:
        raise HireApiError("linked user has no email")
    from ..models.auth import PasswordResetToken
    from ._notifications import send_html_notification_email

    raw = secrets.token_urlsafe(32)
    db.session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=hashlib.sha256(raw.encode()).hexdigest(),
            expires_at=_utcnow() + timedelta(days=7),
        )
    )
    origin = _public_origin()
    url = f"{origin}/page-login.html?reset={raw}"
    send_html_notification_email(
        to=user.email,
        subject="USIS CM login",
        body=f"Set your password:\n{url}\n",
        html_body=f"<p>Set your password to use USIS CM and FinishWorks Field after your start date.</p><p><a href='{url}'>Set password</a></p>",
        from_addr=setting("hire_mail_from", "hr@gousis.com"),
        bcc=setting("hire_mail_from", "hr@gousis.com"),
    )
    _audit(cu=cu, packet=packet, action="send_login", message="Sent login email")
    db.session.commit()
    return {"ok": True}


def payroll_flags(packet: HirePacket, data: dict[str, Any], cu: CurrentUser) -> HirePacket:
    require_hr_full(cu)
    if "de34_filed" in data:
        if data.get("de34_filed"):
            packet.de34_filed_at = packet.de34_filed_at or _utcnow()
            packet.de34_confirmation = str(data.get("de34_confirmation") or packet.de34_confirmation or "")[:80] or None
        else:
            packet.de34_filed_at = None
    if "qb_created" in data:
        if data.get("qb_created"):
            packet.qb_created_at = packet.qb_created_at or _utcnow()
        else:
            packet.qb_created_at = None
    if "qb_list_id" in data:
        packet.qb_list_id = str(data.get("qb_list_id") or "")[:64] or None
    if "pay_by_check" in data:
        packet.pay_by_check = bool(data.get("pay_by_check"))
    if packet.de34_filed_at and packet.qb_created_at:
        packet.stage = "payroll_setup"
        try:
            wf.complete_subject_step(
                process_key=PROCESS_NEW_HIRE,
                subject_type=SUBJECT_HIRE,
                subject_id=packet.id,
                step_key="payroll_setup",
                cu=cu,
            )
        except Exception:
            pass
    if data.get("close"):
        packet.stage = "closed"
        packet.locked_at = _utcnow()
        packet.public_token_hash = None
    _audit(cu=cu, packet=packet, action="payroll_flags", message="Updated payroll setup flags")
    db.session.commit()
    return get_packet(packet.id)


def payroll_gates(packet: HirePacket) -> dict[str, Any]:
    w4 = _tax(packet, "w4")
    de4 = _tax(packet, "de4")
    i9 = packet.i9
    dd = packet.direct_deposit
    notices_ok = bool(packet.notice_acks) and all(a.acknowledged_at for a in packet.notice_acks)
    profile = None
    if packet.user_id:
        profile = db.session.scalar(select(EmployeeTimeProfile).where(EmployeeTimeProfile.user_id == packet.user_id))
    return {
        "w4_signed": bool(w4 and w4.signed_at),
        "de4_signed": bool(de4 and de4.signed_at),
        "i9_section1_signed": bool(i9 and i9.section1_signed_at),
        "i9_section2_signed": bool(i9 and i9.section2_signed_at) or bool(packet.i9_section2_scheduled_at),
        "deposit": bool(packet.pay_by_check) or bool(dd and dd.signed_at),
        "notices": notices_ok,
        "user_linked": bool(packet.user_id),
        "time_profile": bool(profile),
        "clock_eligible_on_start": bool(profile and packet.start_of_work_date and (
            profile.is_clock_eligible or _today_la() >= packet.start_of_work_date
        )),
        "de34_filed": bool(packet.de34_filed_at),
        "qb_created": bool(packet.qb_created_at),
    }


def _csv_row(packet: HirePacket) -> dict[str, str]:
    person = packet.person
    w4 = _w4_fields(packet)
    de4 = _de4_fields(packet)
    dd = packet.direct_deposit
    contacts = list(packet.emergency_contacts or [])
    c1 = contacts[0] if contacts else None
    return {
        "legal_name": _legal_name(person),
        "preferred_name": (person.preferred_name if person else "") or "",
        "email": (person.email if person else "") or packet.invite_email or "",
        "mobile": (person.mobile if person else "") or "",
        "address1": (person.address1 if person else "") or "",
        "city": (person.city if person else "") or "",
        "state": (person.state if person else "") or "",
        "zip": (person.zip if person else "") or "",
        "ssn": decrypt_str(person.ssn_ciphertext) if person else "",
        "dob": decrypt_str(person.dob_ciphertext) if person else "",
        "start_of_work_date": _iso(packet.start_of_work_date) or "",
        "job_title": packet.job_title or "",
        "class": packet.employment_class or "",
        "work_state": packet.work_state or "",
        "w4_filing_status": str(w4.get("filing_status") or ""),
        "w4_step2": str(w4.get("step2") or ""),
        "w4_step3": str(w4.get("step3") or ""),
        "w4_other_income": str(w4.get("step4a") or w4.get("other_income") or ""),
        "w4_deductions": str(w4.get("step4b") or w4.get("deductions") or ""),
        "w4_extra": str(w4.get("step4c") or w4.get("extra_withholding") or ""),
        "w4_exempt": str(w4.get("exempt") or ""),
        "de4_filing_status": str(de4.get("filing_status") or ""),
        "de4_allowances": str(de4.get("regular_allowances") or ""),
        "de4_additional_allowances": str(de4.get("additional_allowances") or ""),
        "de4_extra": str(de4.get("extra_withholding") or ""),
        "de4_exempt": str(de4.get("exempt") or ""),
        "bank_name": (dd.bank_name if dd else "") or "",
        "routing": decrypt_str(dd.routing_ciphertext) if dd else "",
        "account": decrypt_str(dd.account_ciphertext) if dd else "",
        "account_type": (dd.account_type if dd else "") or "",
        "emergency_1": (c1.name if c1 else "") or "",
        "emergency_1_phone": (c1.phone if c1 else "") or "",
    }


def payroll_zip(packet: HirePacket, cu: CurrentUser) -> bytes:
    require_hr_full(cu)
    buf = io.BytesIO()
    ctx = _pdf_ctx(packet)
    person = packet.person
    ctx["ssn"] = decrypt_str(person.ssn_ciphertext) if person else ""
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for key in ("w4", "de4", "i9", "dd_auth", "notices"):
            art = next((a for a in (packet.artifacts or []) if a.artifact_key == key and not a.is_draft), None)
            payload = None
            if art and art.storage_name:
                payload = read_stored_bytes(UploadCategory.HR_HIRE, art.storage_name)
            if not payload:
                payload, name = preview_pdf(packet, key, draft=False)
            else:
                name = f"{key}.pdf"
            zf.writestr(name, payload)
        zf.writestr("de34-worksheet.pdf", render_de34(ctx))
        csv_buf = io.StringIO()
        row = _csv_row(packet)
        writer = csv.DictWriter(csv_buf, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
        zf.writestr("payroll-setup.csv", csv_buf.getvalue())
    payload = buf.getvalue()
    _store_artifact(packet, "payroll_packet", payload, draft=False, filename="payroll-packet.zip")
    _audit(cu=cu, packet=packet, action="download_packet", message="Downloaded payroll packet")
    db.session.commit()
    return payload


def i9_zip(packet: HirePacket, cu: CurrentUser) -> bytes:
    require_hr_full(cu)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        payload, name = preview_pdf(packet, "i9", draft=not bool(packet.employee_signed_at))
        zf.writestr(name or "i9.pdf", payload)
        i9 = packet.i9
        for d in (i9.documents or []) if i9 else []:
            if d.copy_storage_name:
                copy = read_stored_bytes(UploadCategory.HR_HIRE, d.copy_storage_name)
                fname = d.original_filename or f"{d.list_kind}-copy"
                zf.writestr(f"copies/{fname}", copy)
    _audit(cu=cu, packet=packet, action="download_i9", message="Downloaded I-9 packet")
    db.session.commit()
    return buf.getvalue()


def list_audit(packet: HirePacket, cu: CurrentUser) -> dict[str, Any]:
    require_hr_full(cu)
    rows = list(
        db.session.scalars(
            select(AuditLog)
            .where(AuditLog.entity_type == "hire_packet", AuditLog.entity_id == packet.id)
            .order_by(AuditLog.created_at.desc())
        ).all()
    )
    items = []
    for r in rows:
        blob = json.dumps(r.changes or {})
        if "ssn" in blob.lower() and "***" not in blob.lower():
            # belt: never return raw SSN even if an old row slipped through
            changes = _scrub_pii(r.changes)
        else:
            changes = r.changes
        items.append(
            {
                "id": str(r.id),
                "action": r.action,
                "message": r.message,
                "changes": changes,
                "created_at": _iso(r.created_at),
                "user_id": str(r.user_id) if r.user_id else None,
            }
        )
    return {"items": items}


def directory(cu: CurrentUser) -> dict[str, Any]:
    users = list(db.session.scalars(select(User).where(User.is_active.is_(True)).order_by(User.last_name, User.first_name)).all())
    packets = {
        p.user_id: p
        for p in db.session.scalars(select(HirePacket).where(HirePacket.user_id.is_not(None))).all()
    }
    profiles = {
        p.user_id: p for p in db.session.scalars(select(EmployeeTimeProfile)).all()
    }
    full = is_hr_full(cu)
    items = []
    for u in users:
        packet = packets.get(u.id)
        profile = profiles.get(u.id)
        items.append(
            {
                "id": str(u.id),
                "email": u.email if full else None,
                "first_name": u.first_name,
                "last_name": u.last_name,
                "name": " ".join(p for p in (u.first_name, u.last_name) if p) or u.email,
                "hire_stage": packet.stage if packet else None,
                "start_of_work_date": _iso(packet.start_of_work_date) if packet else None,
                "clock_eligible": bool(profile.is_clock_eligible) if profile else False,
                "hire_packet_id": str(packet.id) if packet and full else None,
            }
        )
    return {"items": items}


def run_reminders() -> dict[str, int]:
    from ._notifications import send_html_notification_email

    sent_emp = 0
    sent_hr = 0
    today = _today_la()
    rows = list(
        db.session.scalars(
            select(HirePacket).where(HirePacket.stage.notin_(("void", "closed"))).options(selectinload(HirePacket.i9), selectinload(HirePacket.person))
        ).all()
    )
    from_addr = setting("hire_mail_from", "hr@gousis.com")
    for p in rows:
        start = p.start_of_work_date
        if not start:
            continue
        if start - today <= timedelta(days=2) and start > today and p.employee_signed_at is None and p.invite_email:
            send_html_notification_email(
                to=p.invite_email,
                subject="Please finish your USIS new-hire packet",
                body="Your start date is in two days. Open the link in your invite email to finish and sign.",
                html_body="<p>Your start date is in two days. Please finish and sign your new-hire packet.</p>",
                from_addr=from_addr,
                bcc=from_addr,
            )
            sent_emp += 1
        due_warn = add_business_days(start, 2)
        if today >= due_warn and p.i9 and p.i9.section1_signed_at and not p.i9.section2_signed_at:
            send_html_notification_email(
                to=from_addr,
                subject=f"I-9 Section 2 due — {_display_name(p)}",
                body=f"I-9 Section 2 is due for {_display_name(p)} (start {start.isoformat()}).",
                html_body=f"<p>I-9 Section 2 is due for {_display_name(p)} (start {start.isoformat()}).</p>",
                from_addr=from_addr,
            )
            sent_hr += 1
        if p.user_id:
            user = db.session.get(User, p.user_id)
            _ensure_time_profile(p, user)
    db.session.commit()
    return {"employee_reminders": sent_emp, "hr_reminders": sent_hr}


def artifact_bytes(packet: HirePacket, artifact_key: str, cu: CurrentUser | None, *, allow_public: bool = False) -> tuple[bytes, str, str]:
    if not allow_public:
        assert cu is not None
        require_hr_full(cu)
    draft = True
    if packet.employee_signed_at and artifact_key != "draft":
        draft = False
    payload, name = preview_pdf(packet, artifact_key, draft=draft)
    return payload, name, "application/pdf"
