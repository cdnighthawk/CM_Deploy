"""Tests for hire wizard document upload helpers."""
from __future__ import annotations

from app.services.hr_hire_upload import HR_HIRE_DOC_EXT, resolve_hire_doc_upload


def test_resolve_hire_doc_upload_from_extension():
    resolved = resolve_hire_doc_upload("passport-front.png", "image/png")
    assert resolved == ("passport-front.png", ".png")


def test_resolve_hire_doc_upload_pdf():
    resolved = resolve_hire_doc_upload("scan.pdf", "application/pdf")
    assert resolved == ("scan.pdf", ".pdf")


def test_resolve_hire_doc_upload_infers_from_mime_without_extension():
    resolved = resolve_hire_doc_upload("IMG_1234", "image/jpeg")
    assert resolved == ("IMG_1234.jpg", ".jpg")


def test_resolve_hire_doc_upload_rejects_unknown():
    assert resolve_hire_doc_upload("notes.docx", "application/msword") is None


def test_hire_doc_ext_includes_pdf():
    assert ".pdf" in HR_HIRE_DOC_EXT
