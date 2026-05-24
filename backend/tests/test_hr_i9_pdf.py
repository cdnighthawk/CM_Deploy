"""USCIS I-9 PDF generation from Section 1 JSON."""
from __future__ import annotations

from app.models import User
from app.services.hr_i9_pdf import render_i9_pdf_bytes, section1_to_pdf_fields


def test_section1_to_pdf_fields_mapping():
    user = User(email="jane.doe@example.com", first_name="Jane", last_name="Doe", is_active=True)
    section1 = {
        "last_name": "Doe",
        "first_name": "Jane",
        "middle_initial": "M",
        "address": "123 Main St",
        "city": "Austin",
        "state": "TX",
        "zip": "78701",
        "date_of_birth": "1990-01-15",
        "ssn": "123-45-6789",
        "email": "",
        "telephone": "5125550100",
        "citizenship_status": "citizen",
        "document_choice": "list_a",
        "list_a": {
            "title": "U.S. Passport",
            "issuing_authority": "U.S. Department of State",
            "number": "X12345678",
            "expiration": "2030-06-01",
        },
    }
    fields = section1_to_pdf_fields(section1, user=user)
    assert fields["Last Name (Family Name)"] == "Doe"
    assert fields["First Name Given Name"] == "Jane"
    assert fields["Date of Birth mmddyyyy"] == "01/15/1990"
    assert fields["Employees E-mail Address"] == "jane.doe@example.com"
    assert fields["Document Title 0"] == "U.S. Passport"


def test_render_i9_pdf_bytes(flask_app):
    with flask_app.app_context():
        user = User(email="jane@example.com", first_name="Jane", last_name="Doe", is_active=True)
        section1 = {
            "last_name": "Doe",
            "first_name": "Jane",
            "address": "123 Main St",
            "city": "Austin",
            "state": "TX",
            "zip": "78701",
            "date_of_birth": "1990-01-15",
            "ssn": "123-45-6789",
            "email": "jane@example.com",
            "telephone": "5125550100",
            "citizenship_status": "citizen",
            "document_choice": "list_b_c",
            "list_b": {
                "title": "Driver's license",
                "issuing_authority": "Texas DPS",
                "number": "DL123",
                "expiration": "2028-01-01",
            },
            "list_c": {
                "title": "Social Security Card",
                "issuing_authority": "SSA",
                "number": "123-45-6789",
                "expiration": "N/A",
            },
        }
        pdf = render_i9_pdf_bytes(section1=section1, user=user)
        assert pdf[:4] == b"%PDF"
        assert len(pdf) > 100_000
