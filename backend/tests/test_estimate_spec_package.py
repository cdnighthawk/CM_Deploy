"""Estimating spec-package automation: detect CSI, confirm BOD, draft RFPs (no SMTP)."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.api._estimate_spec_package import (
    canonicalize_manufacturer,
    heuristic_mentions_from_text,
    parse_model_json,
    prefix_matches,
)
from app.extensions import db
from app.models import (
    AuditLog,
    Company,
    Contact,
    Estimate,
    Project,
    Rfp,
    Role,
    SpecSection,
    User,
    UserRole,
)


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def _due():
    return (datetime.now(timezone.utc) + timedelta(days=10)).date().isoformat()


def _staff(client):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="spec_pkg_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Est")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="SpecPkg-" + uuid.uuid4().hex[:8], project_type="commercial")
        v = Company(
            name="Inpro " + uuid.uuid4().hex[:6],
            company_type="vendor",
            email="inpro." + uuid.uuid4().hex[:6] + "@example.com",
        )
        db.session.add_all([p, v])
        db.session.flush()
        c = Contact(company_id=v.id, first_name="Sam", last_name="Rep", email=v.email, is_primary=True)
        est = Estimate(project_id=p.id, name="Finish bid", status="draft")
        db.session.add_all([c, est])
        db.session.commit()
        return {
            "uid": str(u.id),
            "pid": str(p.id),
            "vid": str(v.id),
            "eid": str(est.id),
            "email": v.email,
            "hdr": {"X-Usis-User-Id": str(u.id)},
        }


SAMPLE_JSON = {
    "sections": [
        {
            "csi": "10 26 00",
            "title": "Wall and Door Protection",
            "in_scope_suggestion": True,
            "confidence": 0.86,
            "pages": "10 26 00-1–8",
            "mentions": [
                {
                    "role": "basis_of_design",
                    "manufacturer": "Inpro",
                    "product_line": "IPC",
                    "model_no": "1600",
                    "finish_note": None,
                    "or_equal": True,
                    "substitution_note": "Prior approval 10 days before bid",
                    "page_cite": "2.2.A",
                    "excerpt": "Basis of Design: Inpro IPC Series 1600 crash rail…",
                },
                {
                    "role": "listed_alternate",
                    "manufacturer": "Construction Specialties",
                    "product_line": "Acrovyn",
                    "model_no": None,
                    "or_equal": False,
                    "page_cite": "2.2.B",
                    "excerpt": "Acceptable manufacturers: CS Acrovyn…",
                },
            ],
        },
        {
            "csi": "23 05 00",
            "title": "Common HVAC Requirements",
            "in_scope_suggestion": True,
            "confidence": 0.9,
            "mentions": [],
        },
        {
            "csi": "10 51 00",
            "title": "Lockers",
            "in_scope_suggestion": True,
            "confidence": 0.8,
            "mentions": [
                {
                    "role": "basis_of_design",
                    "manufacturer": "Penco",
                    "product_line": "Vanguard",
                    "model_no": "6-tier",
                    "page_cite": "2.1",
                    "excerpt": "Lockers: Penco Vanguard",
                }
            ],
        },
    ],
    "warnings": ["Addendum 1 replaced BOD paint with Sherwin Duration — see 09 91 00"],
}


def test_spec_package_review_prompt_pack():
    from app.ai.prompts import build_system_prompt

    text = build_system_prompt("spec_package_review")
    assert "spec_package_review" in text
    assert "basis_of_design" in text
    assert "Stay silent on price" in text or "silent on price" in text
    wrapped = "```json\n" + __import__("json").dumps(SAMPLE_JSON) + "\n```"
    data = parse_model_json(wrapped)
    assert len(data["sections"]) == 3
    assert data["sections"][0]["csi"] == "10 26 00"


def test_heuristic_bod_and_alternate():
    text = (
        "SECTION 10 26 00 WALL AND DOOR PROTECTION\n"
        "2.2.A Basis of Design: Inpro IPC Series 1600 crash rail, or equal.\n"
        "Acceptable manufacturers: Construction Specialties, CS Acrovyn.\n"
        "Substitutions require prior approval 10 days before bid."
    )
    rows = heuristic_mentions_from_text(text, page_cite="2.2.A")
    roles = {r["role"] for r in rows}
    assert "basis_of_design" in roles
    assert "listed_alternate" in roles
    mfrs = {r["manufacturer"].lower() for r in rows}
    assert any("inpro" in m for m in mfrs)


def test_prefix_and_alias():
    assert prefix_matches("10 26", "10 26 00")
    assert prefix_matches("09 91", "09 91 23")
    assert not prefix_matches("10 26", "23 05 00")
    assert canonicalize_manufacturer("InPro Corporation") == "Inpro"


def test_empty_state_disables_analyze(client, no_dev_admin):
    ctx = _staff(client)
    r = client.get(f"/api/v1/estimates/{ctx['eid']}/spec-scan", headers=ctx["hdr"])
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    assert body["status_label"] == "No scan"
    assert body["sources"]["analyze_enabled"] is False
    bad = client.post(f"/api/v1/estimates/{ctx['eid']}/spec-scan/analyze", json={}, headers=ctx["hdr"])
    assert bad.status_code == 400
    assert "specification" in (bad.get_json().get("error") or "").lower()


def test_analyze_hides_mep_and_confirms_before_rfp(client, no_dev_admin):
    ctx = _staff(client)
    text = (
        "SECTION 09 91 00 PAINTING\n"
        "SECTION 10 26 00 WALL AND DOOR PROTECTION\n"
        "2.2 Basis of Design: Inpro IPC 1600.\n"
        "Acceptable manufacturers: Construction Specialties.\n"
        "SECTION 22 11 00 FACILITY WATER DISTRIBUTION\n"
        "SECTION 23 05 00 COMMON HVAC REQUIREMENTS\n"
        "SECTION 26 05 00 COMMON ELECTRICAL REQUIREMENTS\n"
    )
    r = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/analyze",
        json={"text": text},
        headers=ctx["hdr"],
    )
    assert r.status_code == 200, r.get_data(as_text=True)
    body = r.get_json()
    codes = {s["csi_code"] for s in body["sections"]}
    assert any(c.startswith("10 26") for c in codes)
    assert any(c.startswith("09 91") for c in codes)
    assert not any(c.startswith("22 ") for c in codes)
    assert not any(c.startswith("23 ") for c in codes)
    assert not any(c.startswith("26 ") for c in codes)
    assert body["out_of_trade_count"] >= 1

    shown = client.get(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan?show_out_of_trade=1",
        headers=ctx["hdr"],
    )
    shown_codes = {s["csi_code"] for s in shown.get_json()["sections"]}
    assert any(c.startswith("22 ") or c.startswith("23 ") or c.startswith("26 ") for c in shown_codes)

    apply = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/apply-model",
        json=SAMPLE_JSON,
        headers=ctx["hdr"],
    )
    assert apply.status_code == 200, apply.get_data(as_text=True)
    sections = apply.get_json()["sections"]
    wall = next(s for s in sections if s["csi_code"].startswith("10 26"))
    roles = {m["mention_role"] for m in wall["mentions"]}
    assert "basis_of_design" in roles
    assert "listed_alternate" in roles
    assert all(m["page_cite"] for m in wall["mentions"] if m["mention_role"] in ("basis_of_design", "listed_alternate"))
    locker = next(s for s in sections if s["csi_code"].startswith("10 51"))
    assert locker["mentions"][0]["match_status"] == "needs_configurator"
    assert locker["mentions"][0]["configurator_key"] == "penco_locker"

    # Unconfirmed mentions must not become RFP lines.
    draft_too_soon = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/draft-rfps",
        json={"vendors": [{"company_id": ctx["vid"], "selected": True}]},
        headers=ctx["hdr"],
    )
    # Need confirm sections first
    assert draft_too_soon.status_code in (400, 404)

    items = [{"id": s["id"], "in_scope": not s["out_of_trade"] and s["csi_code"].startswith(("10 26", "10 51", "09 91"))} for s in sections]
    conf = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/confirm-sections",
        json={"items": items},
        headers=ctx["hdr"],
    )
    assert conf.status_code == 200, conf.get_data(as_text=True)

    # Still unconfirmed mentions: draft may exist as narrative but must not copy those lines.
    premature = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/draft-rfps",
        json={"vendors": [{"company_id": ctx["vid"], "selected": True}]},
        headers=ctx["hdr"],
    )
    if premature.status_code == 201:
        rfp_id = premature.get_json()["rfps"][0]["id"]
        got = client.get(f"/api/v1/rfps/{rfp_id}", headers=ctx["hdr"])
        descs = [ln["description"] for ln in got.get_json()["item"]["line_items"]]
        assert not any("Inpro" in d or "Acrovyn" in d or "Penco" in d for d in descs)

    products = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/confirm-products",
        json={},
        headers=ctx["hdr"],
    )
    assert products.status_code == 200, products.get_data(as_text=True)
    assert products.get_json()["status_label"] in ("Vendors ready", "Review products")

    drafted = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/draft-rfps",
        json={"grouping": "per_vendor", "vendors": [{"company_id": ctx["vid"], "selected": True}]},
        headers=ctx["hdr"],
    )
    assert drafted.status_code == 201, drafted.get_data(as_text=True)
    rfps = drafted.get_json()["rfps"]
    assert rfps
    rfp_id = rfps[0]["id"]
    got = client.get(f"/api/v1/rfps/{rfp_id}", headers=ctx["hdr"])
    item = got.get_json()["item"]
    assert item["status"] == "Draft"
    assert item.get("source_spec_scan_id")
    assert item["sent_at"] is None
    descs = " ".join(ln["description"] for ln in item["line_items"])
    assert "BOD:" in descs or "Inpro" in descs
    assert "unit_cost" not in descs.lower()
    preview = client.get(f"/api/v1/rfps/{rfp_id}/email-preview", headers=ctx["hdr"])
    assert preview.status_code == 200
    assert preview.get_json()["from"] == "quotes@gousis.com"

    with client.application.app_context():
        logs = list(
            db.session.scalars(select(AuditLog).where(AuditLog.entity_type == "estimate_spec_scan")).all()
        )
        actions = {x.action for x in logs}
        assert "start" in actions
        assert "confirm_sections" in actions
        assert "confirm_products" in actions
        assert "draft_rfp" in actions


def test_reanalyze_does_not_mutate_sent_rfp(client, no_dev_admin):
    ctx = _staff(client)
    client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/analyze",
        json={"text": "SECTION 10 26 00 WALL PROTECTION\nBasis of Design: Inpro.", "model_output": SAMPLE_JSON},
        headers=ctx["hdr"],
    )
    got = client.get(f"/api/v1/estimates/{ctx['eid']}/spec-scan", headers=ctx["hdr"])
    sections = got.get_json()["sections"]
    client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/confirm-sections",
        json={"items": [{"id": s["id"], "in_scope": s["csi_code"].startswith("10 26")} for s in sections]},
        headers=ctx["hdr"],
    )
    client.post(f"/api/v1/estimates/{ctx['eid']}/spec-scan/confirm-products", json={}, headers=ctx["hdr"])
    drafted = client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/draft-rfps",
        json={"vendors": [{"company_id": ctx["vid"], "selected": True}]},
        headers=ctx["hdr"],
    )
    assert drafted.status_code == 201, drafted.get_data(as_text=True)
    rfp_id = drafted.get_json()["rfps"][0]["id"]
    with client.application.app_context():
        rfp = db.session.get(Rfp, uuid.UUID(rfp_id))
        rfp.status = "Sent"
        rfp.sent_at = datetime.now(timezone.utc)
        rfp.title = "FROZEN-SENT"
        db.session.commit()
        scan_id = rfp.source_spec_scan_id

    client.post(
        f"/api/v1/estimates/{ctx['eid']}/spec-scan/analyze",
        json={"text": "SECTION 09 91 00 PAINTING\nBasis of Design: Sherwin-Williams."},
        headers=ctx["hdr"],
    )
    with client.application.app_context():
        rfp = db.session.get(Rfp, uuid.UUID(rfp_id))
        assert rfp.title == "FROZEN-SENT"
        assert rfp.status == "Sent"
        assert rfp.source_spec_scan_id == scan_id


def test_spec_register_enables_analyze(client, no_dev_admin):
    ctx = _staff(client)
    with client.application.app_context():
        db.session.add(
            SpecSection(project_id=uuid.UUID(ctx["pid"]), code="10 26 00", title="Wall Protection", is_active=True)
        )
        db.session.commit()
    r = client.get(f"/api/v1/estimates/{ctx['eid']}/spec-scan", headers=ctx["hdr"])
    assert r.status_code == 200
    assert r.get_json()["sources"]["analyze_enabled"] is True
