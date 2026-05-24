"""API tests for project commitments (procurement / Sage-style PO shell)."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.extensions import db
from app.models import Company, CostCode, Project, Role, User, UserRole


@pytest.fixture
def no_dev_admin(monkeypatch):
    monkeypatch.setenv("USIS_API_DEV_ALLOW_ANY", "0")


def test_commitment_crud_line_items_and_bills(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="proc_u_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Buyer")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="Proc-" + uuid.uuid4().hex[:8])
        v = Company(name="Vendor " + uuid.uuid4().hex[:6], company_type="vendor")
        db.session.add_all([p, v])
        db.session.flush()
        pid = str(p.id)
        vid = str(v.id)
        uid = str(u.id)
        cc = CostCode(project_id=p.id, code="09-65-00", description="Acoustical")
        db.session.add(cc)
        db.session.flush()
        ccid = str(cc.id)
        vendor_name = v.name
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": vid,
            "title": "Drywall package",
            "reference_number": "PO-1001",
        },
        headers=hdr,
    )
    assert r.status_code == 201, r.get_data(as_text=True)
    body = r.get_json()
    cid = body["item"]["id"]
    assert body["item"]["status"] == "draft"
    assert body["item"]["vendor_name"] == vendor_name

    r2 = client.get(f"/api/v1/projects/{pid}/commitments", headers=hdr)
    assert r2.status_code == 200
    assert len(r2.get_json()["items"]) == 1

    r3 = client.post(
        f"/api/v1/projects/{pid}/commitments/{cid}/line-items",
        json={
            "description": "GY board",
            "quantity": "120",
            "unit": "SF",
            "unit_cost": "2.50",
            "cost_code_id": ccid,
        },
        headers=hdr,
    )
    assert r3.status_code == 201
    lid = r3.get_json()["item"]["id"]

    r4 = client.post(
        f"/api/v1/projects/{pid}/commitments/{cid}/bill-allocations",
        json={"vendor_bill_ref": "INV-7788", "allocated_amount": "150.00"},
        headers=hdr,
    )
    assert r4.status_code == 201
    bid = r4.get_json()["item"]["id"]

    r5 = client.get(f"/api/v1/projects/{pid}/commitments/{cid}", headers=hdr)
    assert r5.status_code == 200
    d5 = r5.get_json()
    assert len(d5["line_items"]) == 1
    assert len(d5["bill_allocations"]) == 1

    r6 = client.patch(
        f"/api/v1/projects/{pid}/commitments/{cid}",
        json={"status": "approved", "workflow_rule_active": True},
        headers=hdr,
    )
    assert r6.status_code == 200
    assert r6.get_json()["item"]["workflow_rule_active"] is True

    r7 = client.patch(
        f"/api/v1/projects/{pid}/commitments/{cid}/line-items/{lid}",
        json={"description": "GY board (revised)"},
        headers=hdr,
    )
    assert r7.status_code == 403

    r8 = client.patch(
        f"/api/v1/projects/{pid}/commitments/{cid}",
        json={"workflow_rule_active": False},
        headers=hdr,
    )
    assert r8.status_code == 200

    r9 = client.patch(
        f"/api/v1/projects/{pid}/commitments/{cid}/line-items/{lid}",
        json={"description": "GY board (revised)"},
        headers=hdr,
    )
    assert r9.status_code == 200

    r10 = client.delete(
        f"/api/v1/projects/{pid}/commitments/{cid}/bill-allocations/{bid}",
        headers=hdr,
    )
    assert r10.status_code == 204

    r11 = client.delete(
        f"/api/v1/projects/{pid}/commitments/{cid}/line-items/{lid}",
        headers=hdr,
    )
    assert r11.status_code == 204

    r12 = client.delete(f"/api/v1/projects/{pid}/commitments/{cid}", headers=hdr)
    assert r12.status_code == 204

    r13 = client.get(f"/api/v1/projects/{pid}/commitments", headers=hdr)
    assert r13.status_code == 200
    assert r13.get_json()["items"] == []


def test_commitment_list_and_detail_include_rfp_title(client, no_dev_admin):
    """Linked RFP title/status are denormalized on commitment list/detail JSON."""
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="proc_rfp_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Pat", last_name="Buyer")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="ProcRfp-" + uuid.uuid4().hex[:8])
        v = Company(name="Vendor " + uuid.uuid4().hex[:6], company_type="vendor")
        db.session.add_all([p, v])
        db.session.flush()
        pid = str(p.id)
        vid = str(v.id)
        uid = str(u.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}
    r_rfp = client.post("/api/v1/rfps", json={"project_id": pid, "title": "Electrical bid package"}, headers=hdr)
    assert r_rfp.status_code == 201, r_rfp.get_data(as_text=True)
    rfid = r_rfp.get_json()["item"]["id"]

    r_c = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": vid,
            "title": "Linked PO",
            "reference_number": "PO-RFP-1",
            "rfp_id": rfid,
        },
        headers=hdr,
    )
    assert r_c.status_code == 201, r_c.get_data(as_text=True)
    cid = r_c.get_json()["item"]["id"]
    assert r_c.get_json()["item"].get("rfp_title") == "Electrical bid package"

    r_list = client.get(f"/api/v1/projects/{pid}/commitments", headers=hdr)
    assert r_list.status_code == 200
    items = r_list.get_json()["items"]
    assert len(items) == 1
    assert items[0]["rfp_id"] == rfid
    assert items[0].get("rfp_title") == "Electrical bid package"
    assert items[0].get("rfp_status") == "Draft"

    r_detail = client.get(f"/api/v1/projects/{pid}/commitments/{cid}", headers=hdr)
    assert r_detail.status_code == 200
    it = r_detail.get_json()["item"]
    assert it.get("rfp_title") == "Electrical bid package"
    assert it.get("rfp_status") == "Draft"


def test_sage_po_create_with_line_items_and_lookups(client, no_dev_admin):
    with client.application.app_context():
        role = db.session.scalar(select(Role).where(Role.code == "standard"))
        if role is None:
            role = Role(code="standard", name="Standard")
            db.session.add(role)
            db.session.flush()
        u = User(email="proc_sage_" + uuid.uuid4().hex[:8] + "@t.com", first_name="Sam", last_name="Buyer")
        db.session.add(u)
        db.session.flush()
        db.session.add(UserRole(user_id=u.id, role_id=role.id))
        p = Project(name="SagePO-" + uuid.uuid4().hex[:8], address_line1="100 Main St", city="LA", state="CA")
        v = Company(name="Vendor " + uuid.uuid4().hex[:6], company_type="vendor", address_line1="9 Vendor Way")
        db.session.add_all([p, v])
        db.session.flush()
        pid = str(p.id)
        vid = str(v.id)
        uid = str(u.id)
        cc = CostCode(project_id=p.id, code="03-30-00", description="Concrete")
        db.session.add(cc)
        db.session.flush()
        ccid = str(cc.id)
        db.session.commit()

    hdr = {"X-Usis-User-Id": uid}

    r_types = client.get("/api/v1/procurement/po-types", headers=hdr)
    assert r_types.status_code == 200
    assert len(r_types.get_json()["items"]) >= 1

    r_dir = client.get(f"/api/v1/projects/{pid}/directory/companies?q=vendor", headers=hdr)
    assert r_dir.status_code == 200

    r_prof = client.get(f"/api/v1/companies/{vid}/procurement-profile", headers=hdr)
    assert r_prof.status_code == 200
    assert r_prof.get_json()["item"]["address"]

    r_create = client.post(
        f"/api/v1/projects/{pid}/commitments",
        json={
            "commitment_kind": "purchase_order",
            "vendor_company_id": vid,
            "reference_number": "PO-SAGE-99",
            "title": "Concrete package",
            "po_type": "material",
            "ship_to_address": "100 Main St, LA CA",
            "default_tax_code": "TAXABLE",
            "default_resource": "material",
            "line_items": [
                {
                    "item_number": "1",
                    "description": "Ready mix",
                    "quantity": "10",
                    "unit": "CY",
                    "unit_cost": "150",
                    "cost_code_id": ccid,
                    "tax_code": "TAXABLE",
                    "resource": "material",
                }
            ],
        },
        headers=hdr,
    )
    assert r_create.status_code == 201, r_create.get_data(as_text=True)
    body = r_create.get_json()
    assert body["item"]["reference_number"] == "PO-SAGE-99"
    assert body["item"]["po_type"] == "material"
    assert body["item"]["ship_to_address"] == "100 Main St, LA CA"
    assert len(body["line_items"]) == 1
    assert body["line_items"][0]["tax_code"] == "TAXABLE"
    assert body["line_items"][0]["resource"] == "material"
    assert float(body["item"]["total_amount"]) == 1500.0
