"""Safety document merge engine and packet API (Cal/OSHA templates)."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import select

from app.extensions import db
from app.models import Project, ProjectMember, Role, User, UserRole
from app.safety_docs.context import build_context, missing_fields
from app.safety_docs.packet import render_company_docs, render_packet_docs
from app.safety_docs.paths import sample_project_path, seed_company_path
from app.safety_docs.render import render_template


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _company() -> dict:
    return _load_json(seed_company_path())


def _mammoth() -> dict:
    return _load_json(sample_project_path())


def test_empty_superintendent_is_draft_and_lists_missing_fields():
    project = _mammoth()
    miss = missing_fields(project)
    assert "superintendent.name" in miss
    assert "superintendent.phone" in miss
    ctx = build_context(_company(), project, version=1)
    assert ctx["doc"]["missingFields"]
    site = render_packet_docs(_company(), project, version=1)["site-card"]["markdown"]
    assert "DRAFT — NOT FOR MOBILIZATION" in site


def test_scope_scaffolds_omits_or_includes_chapter():
    project = _mammoth()
    project["scope"] = dict(project.get("scope") or {})
    project["scope"]["scaffolds"] = False
    off = render_packet_docs(_company(), project, version=1)["sssp"]["markdown"]
    assert "## 11. Scaffolds" not in off
    project["scope"]["scaffolds"] = True
    on = render_packet_docs(_company(), project, version=1)["sssp"]["markdown"]
    assert "## 11. Scaffolds" in on


def test_company_iipp_has_five_business_days_and_portal_access():
    docs = render_company_docs(_company(), version=1)
    iipp = docs["iipp"]["markdown"]
    assert "five business days" in iipp
    assert "portal" in iipp.lower()
    assert "electronic access" in iipp.lower()


def test_heat_template_triggers_and_no_uc_davis():
    heat = render_company_docs(_company(), version=1)["heat"]["markdown"]
    assert "80°F" in heat
    assert "95°F" in heat
    assert "82°F" in heat
    assert "87°F" in heat
    assert "UC Davis" not in heat
    assert "four-employee" not in heat.lower()
    assert "four employee" not in heat.lower()


def test_wvpp_has_violent_incident_log_and_annual_review():
    wvpp = render_company_docs(_company(), version=1)["wvpp"]["markdown"]
    assert "Violent Incident Log" in wvpp
    assert "annual" in wvpp.lower()


def test_handlebars_if_false_scope_omits_block():
    out = render_template("keep{{#if scope.scaffolds}}SCAFFOLD{{/if}}end", {"scope": {"scaffolds": False}})
    assert out == "keepend"


def _mk_user(prefix: str, role_code: str = "admin") -> User:
    role = db.session.scalar(select(Role).where(Role.code == role_code))
    if role is None:
        role = Role(code=role_code, name=role_code.replace("_", " ").title())
        db.session.add(role)
        db.session.flush()
    u = User(
        email=f"{prefix}_{uuid.uuid4().hex[:8]}@t.com",
        first_name=prefix.title(),
        last_name="Safety",
        is_active=True,
    )
    db.session.add(u)
    db.session.flush()
    db.session.add(UserRole(user_id=u.id, role_id=role.id))
    return u


def test_packet_publish_blocked_when_superintendent_blank(client):
    with client.application.app_context():
        admin = _mk_user("safedocs")
        p = Project(name="Mammoth Draft " + uuid.uuid4().hex[:6], number="ML-" + uuid.uuid4().hex[:4], city="Mammoth Lakes")
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=admin.id, project_id=p.id))
        pid = str(p.id)
        uid = str(admin.id)
        db.session.commit()

    headers = {"X-Usis-User-Id": uid}
    sample = _mammoth()
    r = client.put(f"/api/v1/projects/{pid}/safety-profile", json={"payload": sample}, headers=headers)
    assert r.status_code == 200, r.get_data(as_text=True)
    miss = r.get_json()["item"]["missing_fields"]
    assert "superintendent.name" in miss

    regen = client.post(f"/api/v1/projects/{pid}/safety-packet/regenerate", json={}, headers=headers)
    assert regen.status_code == 200, regen.get_data(as_text=True)
    body = regen.get_json()["item"]
    assert body["status"] == "draft"
    assert body["missing_fields"]

    preview = client.get(f"/api/v1/projects/{pid}/safety-packet/preview", headers=headers)
    assert preview.status_code == 200
    html = preview.get_data(as_text=True)
    assert "DRAFT — NOT FOR MOBILIZATION" in html

    pub = client.post(f"/api/v1/projects/{pid}/safety-packet/publish", json={}, headers=headers)
    assert pub.status_code == 400
    assert "missing" in (pub.get_json() or {}).get("error", "").lower()


def test_publish_succeeds_when_required_fields_filled(client):
    with client.application.app_context():
        admin = _mk_user("safepub")
        p = Project(
            name="Ready Job " + uuid.uuid4().hex[:6],
            number="RJ-" + uuid.uuid4().hex[:4],
            address_line1="100 Main St",
            city="Temecula",
        )
        db.session.add(p)
        db.session.flush()
        db.session.add(ProjectMember(user_id=admin.id, project_id=p.id))
        pid = str(p.id)
        uid = str(admin.id)
        db.session.commit()

    headers = {"X-Usis-User-Id": uid}
    payload = _mammoth()
    payload["superintendent"] = {"name": "Pat Super", "phone": "(209) 555-0100", "title": "Superintendent"}
    payload["address"] = {"line1": "100 Main St", "city": "Temecula", "state": "CA", "zip": "92590"}
    payload["emergency"]["musterPoint"] = "Job trailer"
    payload["emergency"]["whoCalls911"] = "Pat Super"
    payload["emergency"]["directionsFor911"] = "Civic center, gate A"
    payload["emergency"]["hospital"] = {
        "name": "Inland Valley",
        "phone": "(951) 555-0199",
        "address": "Temecula",
    }
    put = client.put(f"/api/v1/projects/{pid}/safety-profile", json={"payload": payload}, headers=headers)
    assert put.status_code == 200, put.get_data(as_text=True)
    pub = client.post(f"/api/v1/projects/{pid}/safety-packet/publish", json={}, headers=headers)
    assert pub.status_code == 200, pub.get_data(as_text=True)
    assert pub.get_json()["item"]["status"] == "published"


def test_company_docs_list_and_iipp_html(client):
    with client.application.app_context():
        admin = _mk_user("safeco")
        uid = str(admin.id)
        db.session.commit()

    headers = {"X-Usis-User-Id": uid}
    listed = client.get("/api/v1/safety/company-docs", headers=headers)
    assert listed.status_code == 200, listed.get_data(as_text=True)
    slugs = {row["slug"] for row in listed.get_json()["items"]}
    assert "iipp" in slugs
    iipp = client.get("/api/v1/safety/company-docs/iipp?format=html", headers=headers)
    assert iipp.status_code == 200
    text = iipp.get_data(as_text=True)
    assert "five business days" in text
    assert "portal" in text.lower()
