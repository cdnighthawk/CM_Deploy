"""CSI catalog, delete spec sections, and spec-book PDF import."""
from __future__ import annotations

import io
import uuid

from pypdf import PdfWriter

from app.csi_catalog import public_catalog, title_for_code
from app.csi_spec import format_csi_display
from app.extensions import db
from app.models import Project, SpecSection
from app.services.spec_book_import import parse_codes_from_text


def _pdf_with_text(text: str) -> bytes:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_outline_item(text, page_number=0)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _pdf_via_reportlab(text: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        return b""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    c.drawString(72, 720, text)
    c.save()
    return buf.getvalue()


def test_format_and_catalog():
    assert format_csi_display("087100") == "08 71 00"
    assert format_csi_display("10 44 16") == "10 44 16"
    assert title_for_code("08 71 00") == "Door Hardware"
    catalog = public_catalog("fire extinguish", 20)
    codes = [row["code"] for row in catalog["items"]]
    assert "10 44 16" in codes
    assert catalog["total"] > 800
    full = public_catalog(None, 5000)
    divisions = {row["division"] for row in full["items"]}
    assert {"00", "08", "09", "10", "23", "26", "34", "35", "49"}.issubset(divisions)


def test_parse_codes_from_spec_text():
    rows = parse_codes_from_text(
        "SECTION 08 71 00 DOOR HARDWARE\n10 44 16 Fire Extinguishers\n087100 extra"
    )
    digits = {row["digits"] for row in rows}
    assert "087100" in digits
    assert "104416" in digits
    hardware = next(row for row in rows if row["digits"] == "087100")
    assert hardware["code"] == "08 71 00"
    assert "Door Hardware" in hardware["title"]


def test_extract_from_outline_pdf():
    from app.services.spec_book_import import extract_csi_sections_from_pdf

    pdf = _pdf_with_text("08 71 00 DOOR HARDWARE")
    rows = extract_csi_sections_from_pdf(pdf)
    assert any(row["code"] == "08 71 00" for row in rows)


def test_csi_sections_api(client):
    r = client.get("/api/v1/csi-sections?q=door%20hardware&limit=20")
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(row["code"] == "08 71 00" for row in items)


def test_add_from_catalog_and_delete(client):
    with client.application.app_context():
        p = Project(name="SpecCat-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    r = client.post(
        f"/api/v1/projects/{pid}/spec-sections/from-catalog",
        json={"codes": ["08 71 00", "104416", "08 71 00"]},
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["created"] == 2
    codes = {item["code"] for item in body["items"]}
    assert codes == {"08 71 00", "10 44 16"}
    titles = {item["code"]: item["title"] for item in body["items"]}
    assert titles["08 71 00"] == "Door Hardware"
    assert titles["10 44 16"] == "Fire Extinguishers"

    r2 = client.post(
        f"/api/v1/projects/{pid}/spec-sections/from-catalog",
        json={"codes": ["08 71 00"]},
    )
    assert r2.status_code == 201
    assert r2.get_json()["created"] == 0

    listed = client.get(f"/api/v1/projects/{pid}/rfi-lookups/spec_sections")
    assert listed.status_code == 200
    items = listed.get_json()["items"]
    assert len(items) == 2
    sid = next(item["id"] for item in items if item["code"] == "08 71 00")

    gone = client.delete(f"/api/v1/projects/{pid}/rfi-lookups/spec_sections/{sid}")
    assert gone.status_code == 200
    listed2 = client.get(f"/api/v1/projects/{pid}/rfi-lookups/spec_sections")
    assert len(listed2.get_json()["items"]) == 1
    assert listed2.get_json()["items"][0]["code"] == "10 44 16"


def test_project_writer_can_delete_spec_section(client, monkeypatch):
    """#17: Delete section must work for projects write, not only admin."""
    from app.models import ProjectMember, Role, RoleModulePermission, User, UserRole

    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    with client.application.app_context():
        p = Project(name="SpecDel-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        role = Role(code="spec_writer_" + uuid.uuid4().hex[:6], name="Spec Writer")
        db.session.add(role)
        db.session.flush()
        db.session.add(RoleModulePermission(role_id=role.id, module_code="projects", access_level="write"))
        u = User(email="specdel_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.add(ProjectMember(user_id=u.id, project_id=p.id))
        db.session.commit()
        pid = str(p.id)
        uid = str(u.id)

    hdr = {"X-Usis-User-Id": uid}
    added = client.post(
        f"/api/v1/projects/{pid}/spec-sections/from-catalog",
        json={"codes": ["08 71 00"]},
        headers=hdr,
    )
    assert added.status_code == 201, added.get_data(as_text=True)
    sid = added.get_json()["items"][0]["id"]

    gone = client.delete(
        f"/api/v1/projects/{pid}/rfi-lookups/spec_sections/{sid}",
        headers=hdr,
    )
    assert gone.status_code == 200, gone.get_data(as_text=True)
    listed = client.get(f"/api/v1/projects/{pid}/rfi-lookups/spec_sections", headers=hdr)
    assert listed.get_json()["items"] == []


def test_project_reader_cannot_delete_spec_section(client, monkeypatch):
    from app.models import ProjectMember, Role, RoleModulePermission, User, UserRole

    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")
    with client.application.app_context():
        p = Project(name="SpecRead-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        role = Role(code="spec_reader_" + uuid.uuid4().hex[:6], name="Spec Reader")
        db.session.add(role)
        db.session.flush()
        db.session.add(RoleModulePermission(role_id=role.id, module_code="projects", access_level="read"))
        u = User(email="specread_" + uuid.uuid4().hex[:8] + "@t.com", is_active=True)
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        db.session.add(ProjectMember(user_id=u.id, project_id=p.id))
        row = SpecSection(project_id=p.id, code="08 71 00", title="Door Hardware", is_active=True)
        db.session.add(row)
        db.session.commit()
        pid = str(p.id)
        uid = str(u.id)
        sid = str(row.id)

    blocked = client.delete(
        f"/api/v1/projects/{pid}/rfi-lookups/spec_sections/{sid}",
        headers={"X-Usis-User-Id": uid},
    )
    assert blocked.status_code == 403


def test_import_spec_book_pdf(client):
    with client.application.app_context():
        p = Project(name="SpecImp-" + uuid.uuid4().hex[:8])
        db.session.add(p)
        db.session.flush()
        pid = str(p.id)
        db.session.commit()

    text = "08 71 00 DOOR HARDWARE"
    pdf = _pdf_via_reportlab(text)
    if not pdf:
        pdf = _pdf_with_text(text)
    data = {"file": (io.BytesIO(pdf), "spec-book.pdf")}
    r = client.post(
        f"/api/v1/projects/{pid}/spec-book/import",
        data=data,
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    assert body["found"] >= 1
    assert body["created"] >= 1
    assert any(item["code"] == "08 71 00" for item in body["items"])

    with client.application.app_context():
        rows = db.session.query(SpecSection).filter(SpecSection.project_id == uuid.UUID(pid)).all()
        assert any(row.code == "08 71 00" for row in rows)
