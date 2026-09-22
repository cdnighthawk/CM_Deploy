"""WorX CM product chrome vs USIS company mail/careers."""
from __future__ import annotations

from pathlib import Path

from app.branding import company_email_header_html, product_wordmark_html

REPO = Path(__file__).resolve().parents[2]
GULP = REPO / "W3CRM-v3.0-13_September_2025" / "gulp"
SRC = GULP / "src"


def test_product_mark_assets_exist():
    for name in ("worx-cm-icon.svg", "worx-cm-lockup.svg", "usis-eagle-logo.png"):
        assert (SRC / "assets/images/branding" / name).is_file()
        assert (GULP / "dist/assets/images/branding" / name).is_file()
    static = REPO / "backend/app/static/branding"
    assert (static / "worx-cm-icon.svg").is_file()
    assert (static / "usis-eagle-logo.png").is_file()


def test_staff_header_uses_worx_mark():
    brand = (SRC / "elements/nav-brand-usis.html").read_text(encoding="utf-8")
    assert "worx-cm-icon.svg" in brand
    assert "usis-eagle-logo.png" not in brand
    assert "WorX" in brand and "CM" in brand


def test_staff_login_uses_worx_mark():
    login = (SRC / "page-login.html").read_text(encoding="utf-8")
    staff, applicant = login.split('id="usis-login-applicant"', 1)
    assert "worx-cm-icon.svg" in staff
    assert "usis-eagle-logo.png" not in staff
    assert "usis-eagle-logo.png" in applicant
    assert "Apply to USIS" in login
    assert "USIS employees" in login


def test_careers_keep_eagle_and_usis():
    apply_html = (SRC / "apply.html").read_text(encoding="utf-8")
    assert "usis-eagle-logo.png" in apply_html
    assert "Apply at USIS" in apply_html
    public = (SRC / "elements/header-public.html").read_text(encoding="utf-8")
    assert "usis-eagle-logo.png" in public
    assert "US Interior Specialties" in public
    register = (SRC / "page-register.html").read_text(encoding="utf-8")
    assert "usis-eagle-logo.png" in register
    assert "worx-cm-icon.svg" not in register


def test_company_email_uses_usis_eagle():
    html = (REPO / "backend/app/templates/email/hire_invite.html").read_text(encoding="utf-8")
    assert "USIS" in html
    assert "eagle_url" in html
    assert "WorX" not in html
    header = company_email_header_html("https://www.usiscm.com")
    assert "usis-eagle-logo.png" in header
    assert ">USIS<" in header.replace(" ", "") or "USIS</span>" in header
    assert "WorX" not in header


def test_product_wordmark_uses_worx_icon():
    mark = product_wordmark_html()
    assert "worx-cm-icon.svg" in mark
    assert "WorX" in mark
    assert "usis-eagle" not in mark
