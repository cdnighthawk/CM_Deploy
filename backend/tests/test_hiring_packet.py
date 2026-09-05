"""New-hire packet: encryption, public token, W-4/DE-4, I-9 §2, payroll export."""
from __future__ import annotations

import io
import uuid
import zipfile
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.extensions import db
from app.models import EmployeeTimeProfile, Role, User, UserRole
from app.models.hiring import HirePacket
from app.services.hire_crypto import decrypt_str, encrypt_str, hash_token, last4
from app.services.hire_forms import NOTICE_KEYS
from app.services.hire_validate import aba_routing_valid, normalize_ssn


def _role(code: str) -> Role:
    role = db.session.scalar(select(Role).where(Role.code == code))
    if role is None:
        role = Role(code=code, name=code)
        db.session.add(role)
        db.session.flush()
    return role


def _user(prefix: str, *, hr: bool = False) -> User:
    u = User(
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@t.com",
        first_name=prefix,
        last_name="Hire",
        is_active=True,
        is_superuser=False,
    )
    db.session.add(u)
    db.session.flush()
    if hr:
        role = _role("hr_admin")
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def test_encrypt_decrypt_roundtrip_and_last4(flask_app):
    with flask_app.app_context():
        blob = encrypt_str("123-45-6789")
        assert blob
        assert "123-45-6789" not in blob
        assert decrypt_str(blob) == "123-45-6789"
        assert last4("123-45-6789") == "6789"
        assert hash_token("abc") == hash_token("abc")
        assert hash_token("abc") != hash_token("abd")
        assert normalize_ssn("123456789") == "123-45-6789"
        assert aba_routing_valid("021000021")


def test_token_guess_expired_voided_404(client):
    with client.application.app_context():
        hr = _user("hrg", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    created = client.post(
        "/api/hires",
        json={"job_title": "Painter", "start_of_work_date": "2026-10-01", "invite_email": f"p_{uuid.uuid4().hex[:6]}@e.com"},
        headers=headers,
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    pid = created.get_json()["id"]
    invited = client.post(f"/api/hires/{pid}/invite", json={}, headers=headers)
    assert invited.status_code == 200, invited.get_data(as_text=True)
    token = invited.get_json()["invite_url"].rstrip("/").rsplit("/", 1)[-1]
    assert client.get(f"/api/public/hire/{token}").status_code == 200
    assert client.get("/api/public/hire/not-a-real-token-value-at-all-xx").status_code == 404
    with client.application.app_context():
        row = db.session.get(HirePacket, uuid.UUID(pid))
        row.token_expires_at = datetime.now(tz=timezone.utc) - timedelta(days=1)
        db.session.commit()
    assert client.get(f"/api/public/hire/{token}").status_code == 404
    client.post(
        f"/api/hires/{pid}/invite",
        json={},
        headers=headers,
    )
    invited2 = client.post(f"/api/hires/{pid}/resend", json={}, headers=headers)
    token2 = invited2.get_json()["invite_url"].rstrip("/").rsplit("/", 1)[-1]
    voided = client.post(f"/api/hires/{pid}/void", json={"reason": "offer withdrawn"}, headers=headers)
    assert voided.status_code == 200
    assert client.get(f"/api/public/hire/{token2}").status_code == 404


def test_public_cannot_set_start_or_section2(client):
    with client.application.app_context():
        hr = _user("hrb", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    created = client.post(
        "/api/hires",
        json={"job_title": "Finisher", "start_of_work_date": "2026-11-02", "invite_email": f"f_{uuid.uuid4().hex[:6]}@e.com"},
        headers=headers,
    )
    pid = created.get_json()["id"]
    token = client.post(f"/api/hires/{pid}/invite", json={}, headers=headers).get_json()["invite_url"].rsplit("/", 1)[-1]
    denied = client.patch(
        f"/api/public/hire/{token}",
        json={"step": 2, "start_of_work_date": "1999-01-01", "person": {"legal_first": "A"}},
    )
    assert denied.status_code == 400
    denied2 = client.patch(f"/api/public/hire/{token}", json={"i9_section2": {"sign": True}})
    assert denied2.status_code == 400
    saved = client.patch(
        f"/api/public/hire/{token}",
        json={
            "step": 2,
            "person": {
                "legal_first": "Ada",
                "legal_last": "Finisher",
                "dob": "1991-02-03",
                "ssn": "123-45-6789",
                "email": "ada.finisher@e.com",
            },
        },
    )
    assert saved.status_code == 200, saved.get_data(as_text=True)


def _invite(client, headers, email=None, start="2026-12-01"):
    mail = email or f"e_{uuid.uuid4().hex[:6]}@e.com"
    created = client.post(
        "/api/hires",
        json={"job_title": "Painter", "start_of_work_date": start, "invite_email": mail},
        headers=headers,
    )
    assert created.status_code == 201, created.get_data(as_text=True)
    pid = created.get_json()["id"]
    invited = client.post(f"/api/hires/{pid}/invite", json={}, headers=headers)
    assert invited.status_code == 200, invited.get_data(as_text=True)
    token = invited.get_json()["invite_url"].rsplit("/", 1)[-1]
    return pid, token, invited.get_json()


def _acks():
    return {k: True for k, _t in NOTICE_KEYS}


_PNG = (
    "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _fill_public(client, token, *, first="Pat", last="Painter", email=None):
    mail = email or f"pat_{uuid.uuid4().hex[:6]}@e.com"
    saved = client.patch(
        f"/api/public/hire/{token}",
        json={
            "step": 7,
            "person": {
                "legal_first": first,
                "legal_last": last,
                "ssn": "123-45-6789",
                "dob": "1990-01-02",
                "email": mail,
                "mobile": "555-0100",
                "address1": "1 Main",
                "city": "LA",
                "state": "CA",
                "zip": "90012",
            },
            "i9": {"attestation": "us_citizen"},
            "w4": {"filing_status": "single_or_mfs", "exempt": False, "step3": 0},
            "de4": {"filing_status": "single", "regular_allowances": 1},
            "direct_deposit": {
                "bank_name": "Chase",
                "routing": "021000021",
                "account": "123456789",
                "account_type": "checking",
                "account_holder_name": f"{first} {last}",
            },
            "emergency_contacts": [
                {"name": "Ann", "relation": "Spouse", "phone": "555-0101"},
                {"name": "Bob", "relation": "Parent", "phone": "555-0102"},
            ],
            "notice_acks": _acks(),
        },
    )
    assert saved.status_code == 200, saved.get_data(as_text=True)
    return saved


def _sign_public(client, token, typed_name="Pat Painter"):
    signed = client.post(
        f"/api/public/hire/{token}/sign",
        json={
            "typed_legal_name": typed_name,
            "signature_png": _PNG,
            "certifications": {"w4": True, "i9": True, "de4": True, "dd_auth": True, "notices": True},
        },
    )
    assert signed.status_code == 200, signed.get_data(as_text=True)
    return signed


def test_w4_exempt_zeros_and_de4_kept(client):
    with client.application.app_context():
        hr = _user("hrw", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    pid, token, meta = _invite(client, headers)
    assert meta.get("workflow_definition_version") is not None
    assert meta.get("form_pack_version_id")
    client.patch(
        f"/api/public/hire/{token}",
        json={"step": 4, "person": {"legal_first": "Pat", "legal_last": "Painter", "ssn": "123-45-6789", "dob": "1990-01-02"}, "w4": {"filing_status": "single_or_mfs", "exempt": True, "step2": True, "step3": 2000, "step4a": 50}},
    )
    client.patch(
        f"/api/public/hire/{token}",
        json={"step": 5, "de4": {"filing_status": "single", "regular_allowances": 3, "extra_withholding": 25}},
    )
    with client.application.app_context():
        packet = db.session.get(HirePacket, uuid.UUID(pid))
        w4 = next(t for t in packet.tax_elections if t.form_key == "w4")
        de4 = next(t for t in packet.tax_elections if t.form_key == "de4")
        assert w4.fields.get("exempt") is True
        assert w4.fields.get("step2") is False
        assert w4.fields.get("step3") in (0, "0")
        assert de4.fields.get("regular_allowances") in (3, "3")
        assert packet.workflow_definition_version == meta["workflow_definition_version"]


def test_i9_section2_rejects_list_a_and_b(client):
    with client.application.app_context():
        hr = _user("hri", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    pid, token, _ = _invite(client, headers)
    client.patch(
        f"/api/public/hire/{token}",
        json={"step": 3, "person": {"legal_first": "Pat", "legal_last": "Painter", "ssn": "123-45-6789", "dob": "1990-01-02"}, "i9": {"attestation": "us_citizen"}},
    )
    # Section 1 must be signed for §2 — sign path blocked without full packet; call §2 anyway to hit unsigned §1
    r = client.post(
        f"/api/hires/{pid}/i9/section2",
        json={
            "document_list_mode": "A",
            "documents": [
                {"list_kind": "A", "document_title": "Passport"},
                {"list_kind": "B", "document_title": "DL"},
            ],
            "first_day_of_employment": "2026-12-01",
        },
        headers=headers,
    )
    assert r.status_code in (400, 409)


def test_sign_without_certifications_fails(client):
    with client.application.app_context():
        hr = _user("hrs", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    _pid, token, _ = _invite(client, headers)
    r = client.post(
        f"/api/public/hire/{token}/sign",
        json={"typed_legal_name": "Pat Painter", "signature_png": "data:image/png;base64,aa", "certifications": {}},
    )
    assert r.status_code == 400


def test_ssn_not_in_audit_and_payroll_403_and_link_user(client):
    with client.application.app_context():
        hr = _user("hra", hr=True)
        other = _user("crew", hr=False)
        db.session.commit()
        hid, oid = str(hr.id), str(other.id)
    headers = {"X-Usis-User-Id": hid}
    pid, token, _ = _invite(client, headers, start="2099-01-15")
    client.patch(
        f"/api/public/hire/{token}",
        json={
            "step": 7,
            "person": {
                "legal_first": "Pat",
                "legal_last": "Painter",
                "ssn": "123-45-6789",
                "dob": "1990-01-02",
                "email": f"pat_{uuid.uuid4().hex[:6]}@e.com",
                "mobile": "555-0100",
                "address1": "1 Main",
                "city": "LA",
                "state": "CA",
                "zip": "90012",
            },
            "i9": {"attestation": "us_citizen"},
            "w4": {"filing_status": "single_or_mfs", "exempt": False, "step3": 0},
            "de4": {"filing_status": "single", "regular_allowances": 1},
            "direct_deposit": {"bank_name": "Chase", "routing": "021000021", "account": "123456789", "account_type": "checking", "account_holder_name": "Pat Painter"},
            "emergency_contacts": [
                {"name": "Ann", "relation": "Spouse", "phone": "555-0101"},
                {"name": "Bob", "relation": "Parent", "phone": "555-0102"},
            ],
            "notice_acks": _acks(),
        },
    )
    preview = client.get(f"/api/public/hire/{token}/preview/i9")
    assert preview.status_code == 200
    import fitz

    text = "".join(page.get_text() for page in fitz.open(stream=preview.data, filetype="pdf"))
    assert "01/20/25" in text
    assert "05/31/2027" in text
    signed = client.post(
        f"/api/public/hire/{token}/sign",
        json={
            "typed_legal_name": "Pat Painter",
            "signature_png": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            "certifications": {"w4": True, "i9": True, "de4": True, "dd_auth": True, "notices": True},
        },
    )
    assert signed.status_code == 200, signed.get_data(as_text=True)
    audit = client.get(f"/api/hires/{pid}/audit", headers=headers)
    assert audit.status_code == 200
    blob = audit.get_data(as_text=True).lower()
    assert "123-45-6789" not in blob
    denied = client.get(f"/api/hires/{pid}/payroll-packet", headers={"X-Usis-User-Id": oid})
    assert denied.status_code == 403
    linked = client.post(f"/api/hires/{pid}/link-user", json={}, headers=headers)
    assert linked.status_code == 200, linked.get_data(as_text=True)
    uid = linked.get_json()["user_id"]
    again = client.post(f"/api/hires/{pid}/link-user", json={}, headers=headers)
    assert again.get_json()["user_id"] == uid
    assert again.get_json()["created"] is False
    with client.application.app_context():
        n = db.session.scalar(select(func.count()).select_from(User).where(User.id == uuid.UUID(uid)))
        assert n == 1
        profile = db.session.scalar(select(EmployeeTimeProfile).where(EmployeeTimeProfile.user_id == uuid.UUID(uid)))
        assert profile is not None
        assert profile.is_clock_eligible is False
    s2 = client.post(
        f"/api/hires/{pid}/i9/section2",
        json={
            "sign": True,
            "signature_png": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==",
            "first_day_of_employment": "2099-01-15",
            "document_list_mode": "A",
            "documents": [{"list_kind": "A", "document_title": "U.S. Passport", "issuing_authority": "State", "document_number": "X1"}],
            "examiner_title": "HR",
        },
        headers=headers,
    )
    assert s2.status_code == 200, s2.get_data(as_text=True)
    mixed = client.post(
        f"/api/hires/{pid}/i9/section2",
        json={
            "documents": [
                {"list_kind": "A", "document_title": "Passport"},
                {"list_kind": "B", "document_title": "DL"},
            ],
            "first_day_of_employment": "2099-01-15",
        },
        headers=headers,
    )
    assert mixed.status_code == 400
    z = client.get(f"/api/hires/{pid}/payroll-packet", headers=headers)
    assert z.status_code == 200
    assert z.mimetype == "application/zip"


def test_mailing_address_persisted_when_not_same(client):
    with client.application.app_context():
        hr = _user("hrm", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    _pid, token, _ = _invite(client, headers)
    saved = client.patch(
        f"/api/public/hire/{token}",
        json={
            "step": 2,
            "person": {
                "legal_first": "Ada",
                "legal_last": "Mailer",
                "dob": "1991-02-03",
                "ssn": "123-45-6789",
                "email": "ada.mailer@e.com",
                "address1": "1 Home St",
                "city": "LA",
                "state": "CA",
                "zip": "90012",
                "mailing_same_as_residential": False,
                "mailing_address1": "9 PO Box",
                "mailing_city": "Fresno",
                "mailing_state": "CA",
                "mailing_zip": "93721",
            },
        },
    )
    assert saved.status_code == 200, saved.get_data(as_text=True)
    person = saved.get_json()["person"]
    assert person["mailing_same_as_residential"] is False
    assert person["mailing_address1"] == "9 PO Box"
    assert person["mailing_city"] == "Fresno"
    assert person["mailing_zip"] == "93721"
    pub = client.get(f"/api/public/hire/{token}").get_json()
    assert "Step 1(c)" in (pub.get("w4_step_wording") or {}).get("step1c", "")
    assert "I claim exemption from withholding for 2026" in (pub.get("w4_exempt_text") or "")
    notice = client.get(f"/api/public/hire/{token}/preview/notice_2810_5")
    assert notice.status_code == 200
    assert notice.mimetype == "application/pdf"


def test_send_back_clears_signatures_and_allows_public_patch(client):
    with client.application.app_context():
        hr = _user("hrs", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    pid, token, _ = _invite(client, headers)
    _fill_public(client, token)
    _sign_public(client, token)
    locked = client.patch(f"/api/public/hire/{token}", json={"step": 2, "person": {"legal_first": "Pat"}})
    assert locked.status_code == 409
    back = client.post(f"/api/hires/{pid}/send-back", json={"note": "Fix SSN"}, headers=headers)
    assert back.status_code == 200, back.get_data(as_text=True)
    opened = client.get(f"/api/public/hire/{token}")
    assert opened.status_code == 200
    assert opened.get_json().get("readonly") is False
    again = client.patch(
        f"/api/public/hire/{token}",
        json={"step": 2, "person": {"legal_first": "Pat", "legal_last": "Painter"}},
    )
    assert again.status_code == 200, again.get_data(as_text=True)


def test_non_hr_list_redacts_form_chips(client):
    with client.application.app_context():
        hr = _user("hrn", hr=True)
        other = _user("crew2", hr=False)
        db.session.commit()
        hid, oid = str(hr.id), str(other.id)
    headers = {"X-Usis-User-Id": hid}
    pid, _token, _ = _invite(client, headers)
    listed = client.get("/api/hires", headers={"X-Usis-User-Id": oid})
    assert listed.status_code == 200, listed.get_data(as_text=True)
    items = listed.get_json()["items"]
    row = next(r for r in items if r["id"] == pid)
    assert set(row) <= {"id", "employee", "start_of_work_date", "stage"}
    blob = listed.get_data(as_text=True).lower()
    assert "123-45-6789" not in blob
    assert "ssn" not in blob


def test_i9_only_zip_hr_ok_non_hr_forbidden(client):
    with client.application.app_context():
        hr = _user("hrz", hr=True)
        other = _user("crewz", hr=False)
        db.session.commit()
        hid, oid = str(hr.id), str(other.id)
    headers = {"X-Usis-User-Id": hid}
    pid, token, _ = _invite(client, headers, start="2099-02-01")
    _fill_public(client, token)
    _sign_public(client, token)
    s2 = client.post(
        f"/api/hires/{pid}/i9/section2",
        json={
            "sign": True,
            "signature_png": _PNG,
            "first_day_of_employment": "2099-02-01",
            "document_list_mode": "A",
            "documents": [
                {
                    "list_kind": "A",
                    "document_title": "U.S. Passport",
                    "issuing_authority": "State",
                    "document_number": "X1",
                    "expiration_na": True,
                }
            ],
            "examiner_title": "HR",
        },
        headers=headers,
    )
    assert s2.status_code == 200, s2.get_data(as_text=True)
    denied = client.get(f"/api/hires/{pid}/i9-packet", headers={"X-Usis-User-Id": oid})
    assert denied.status_code == 403
    z = client.get(f"/api/hires/{pid}/i9-packet", headers=headers)
    assert z.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(z.data)).namelist()
    joined = " ".join(names).lower()
    assert "i9" in joined
    assert "w4" not in joined
    assert "payroll-setup.csv" not in joined
    assert not any(n.lower().endswith(".csv") for n in names)


def test_link_user_409_on_duplicate_legal_name(client):
    with client.application.app_context():
        hr = _user("hrd", hr=True)
        db.session.add(
            User(
                email=f"j1_{uuid.uuid4().hex[:6]}@t.com",
                first_name="Jordan",
                last_name="Mason",
                is_active=True,
            )
        )
        db.session.add(
            User(
                email=f"j2_{uuid.uuid4().hex[:6]}@t.com",
                first_name="Jordan",
                last_name="Mason",
                is_active=True,
            )
        )
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    pid, token, _ = _invite(client, headers, email=f"unique_{uuid.uuid4().hex[:6]}@e.com")
    _fill_public(client, token, first="Jordan", last="Mason", email=f"hire_{uuid.uuid4().hex[:6]}@e.com")
    linked = client.post(f"/api/hires/{pid}/link-user", json={}, headers=headers)
    assert linked.status_code == 409, linked.get_data(as_text=True)
    body = linked.get_json()
    assert len(body.get("candidates") or []) == 2


def test_public_api_403_over_http_when_production(client, monkeypatch):
    with client.application.app_context():
        hr = _user("hrp", hr=True)
        db.session.commit()
        hid = str(hr.id)
    headers = {"X-Usis-User-Id": hid}
    _pid, token, _ = _invite(client, headers)
    monkeypatch.setenv("FLASK_ENV", "production")
    denied = client.get(f"/api/public/hire/{token}")
    assert denied.status_code == 403
    ok = client.get(f"/api/public/hire/{token}", environ_overrides={"wsgi.url_scheme": "https"})
    assert ok.status_code == 200
