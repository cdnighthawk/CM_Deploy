"""Fill hire-form PDFs.

Official blanks are not shipped. Until HR uploads an IRS/USCIS/EDD AcroForm,
this module draws a labeled **USIS working copy** with the required W-4 step
wording, I-9 edition ``01/20/25`` / expiration ``05/31/2027``, and packet fields.
If ``uses_official_blank`` and a fillable PDF exist, AcroForm fields are filled
via pypdf using ``FormTemplate.field_map``.
"""
from __future__ import annotations

import hashlib
import io
from datetime import date
from pathlib import Path
from typing import Any

from flask import current_app

from .hire_forms import I9_EDITION, I9_EXPIRATION, W4_EXEMPT_TEXT

_WORKING = "USIS WORKING COPY — replace with the official downloaded form before an audit print."


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _wrap(text: str, width: int = 96) -> list[str]:
    words = (text or "").split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = (cur + " " + w).strip()
        if len(trial) > width:
            if cur:
                lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


def _draw_working_copy(
    title: str,
    rows: list[tuple[str, str]],
    *,
    watermark: bool = False,
    footer: str | None = None,
    extra_paragraphs: list[str] | None = None,
    signature_png: str | None = None,
) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    y = 36
    page.insert_text((36, y), _WORKING, fontsize=8, color=(0.45, 0.15, 0.1))
    y += 18
    page.insert_text((36, y), title, fontsize=14, color=(0.12, 0.31, 0.37))
    y += 22
    if watermark:
        page.insert_text((220, 400), "DRAFT", fontsize=48, color=(0.85, 0.85, 0.85), rotate=0)
        page.insert_text((36, y), "DRAFT — not signed", fontsize=10, color=(0.5, 0.2, 0.1))
        y += 16
    for label, value in rows:
        page.insert_text((36, y), f"{label}:", fontsize=9, color=(0.2, 0.2, 0.2))
        page.insert_text((200, y), (value or "—")[:90], fontsize=9)
        y += 14
        if y > 740:
            page = doc.new_page(width=612, height=792)
            y = 36
    for para in extra_paragraphs or []:
        y += 8
        for line in _wrap(para, 92):
            page.insert_text((36, y), line, fontsize=8)
            y += 12
            if y > 740:
                page = doc.new_page(width=612, height=792)
                y = 36
    if signature_png:
        y += 10
        page.insert_text((36, y), "Signature:", fontsize=9)
        y += 6
        try:
            raw = signature_png
            if "," in raw[:80]:
                import base64

                payload = base64.b64decode(raw.split(",", 1)[1])
            else:
                import base64

                payload = base64.b64decode(raw)
            rect = fitz.Rect(36, y, 260, y + 50)
            page.insert_image(rect, stream=payload)
            y += 56
        except Exception:
            page.insert_text((36, y + 12), "(signature image could not be embedded)", fontsize=8)
            y += 20
    if footer:
        page.insert_text((36, 770), footer[:110], fontsize=8, color=(0.3, 0.3, 0.3))
    return doc.tobytes()


def _try_fill_acroform(blank_path: str, field_values: dict[str, str], watermark: bool) -> bytes | None:
    path = Path(blank_path)
    if not path.is_file():
        return None
    try:
        from pypdf import PdfReader, PdfWriter

        reader = PdfReader(str(path))
        writer = PdfWriter()
        writer.append(reader)
        if writer.get_fields():
            writer.update_page_form_field_values(writer.pages[0], field_values)
        buf = io.BytesIO()
        writer.write(buf)
        payload = buf.getvalue()
        if watermark:
            import fitz

            doc = fitz.open(stream=payload, filetype="pdf")
            for page in doc:
                page.insert_text((200, 400), "DRAFT", fontsize=48, color=(0.85, 0.85, 0.85))
            payload = doc.tobytes()
        return payload
    except Exception:
        current_app.logger.exception("hire acroform fill failed; falling back to working copy")
        return None


def render_w4(ctx: dict[str, Any], *, draft: bool, signature_png: str | None = None) -> bytes:
    exempt = bool(ctx.get("exempt"))
    rows = [
        ("Employee name", ctx.get("legal_name") or ""),
        ("Address", ctx.get("address") or ""),
        ("SSN (last 4)", ctx.get("ssn_last4") or ""),
        ("Step 1(c) filing status", ctx.get("filing_status") or ""),
        ("Step 2 multiple jobs", "Yes" if ctx.get("step2") and not exempt else "No"),
        ("Step 3 credits", "0" if exempt else str(ctx.get("step3") or "0")),
        ("Step 4(a) other income", "0" if exempt else str(ctx.get("step4a") or "0")),
        ("Step 4(b) deductions", "0" if exempt else str(ctx.get("step4b") or "0")),
        ("Step 4(c) extra withholding", "0" if exempt else str(ctx.get("step4c") or "0")),
        ("Exempt from withholding", "Yes — " + W4_EXEMPT_TEXT[:80] if exempt else "No"),
        ("Signed", ctx.get("signed_at") or ("pending" if draft else "")),
    ]
    extra = [
        "Form W-4 (2026) Steps 1(c) through 4(c). Do not simplify this form. "
        "This working copy carries the IRS-required step structure for USIS CM until an official blank is mapped.",
        "Step 1(c): Single or Married filing separately | Married filing jointly | Head of household.",
        "Step 2: Complete this step if you (1) hold more than one job at a time, or (2) are married filing jointly and your spouse also works.",
        "Step 3: Claim dependents and other credits (dollar amount).",
        "Step 4(a) Other income; 4(b) Deductions; 4(c) Extra withholding per pay period.",
    ]
    if exempt:
        extra.append(W4_EXEMPT_TEXT)
    extra.append(
        "Under penalties of perjury, I declare that this certificate, to the best of my knowledge and belief, "
        "is true, correct, and complete."
    )
    return _draw_working_copy(
        "Form W-4 Employee's Withholding Certificate (2026)",
        rows,
        watermark=draft,
        extra_paragraphs=extra,
        signature_png=signature_png,
        footer="USIS working copy of Form W-4 2026",
    )


def render_i9(ctx: dict[str, Any], *, draft: bool, signature_png: str | None = None) -> bytes:
    rows = [
        ("Last name", ctx.get("legal_last") or ""),
        ("First name", ctx.get("legal_first") or ""),
        ("Middle", ctx.get("legal_middle") or ""),
        ("Address", ctx.get("address") or ""),
        ("Date of birth", ctx.get("dob") or ""),
        ("SSN (last 4)", ctx.get("ssn_last4") or ""),
        ("Email", ctx.get("email") or ""),
        ("Telephone", ctx.get("mobile") or ""),
        ("Section 1 attestation", ctx.get("attestation") or ""),
        ("USCIS / A-number", ctx.get("uscis_a_number") or ""),
        ("I-94", ctx.get("i94_number") or ""),
        ("Foreign passport", ctx.get("foreign_passport_number") or ""),
        ("Work until", ctx.get("work_until") or ""),
        ("Section 1 signed", ctx.get("section1_signed_at") or ("pending" if draft else "")),
        ("First day of employment", ctx.get("first_day") or ""),
        ("List mode", ctx.get("document_list_mode") or ""),
        ("List A / B / C", ctx.get("documents_summary") or ""),
        ("Examiner", ctx.get("examiner_name") or ""),
        ("Examiner title", ctx.get("examiner_title") or ""),
        ("Employer", ctx.get("employer_business_name") or ""),
        ("Employer address", ctx.get("employer_address") or ""),
        ("Section 2 signed", ctx.get("section2_signed_at") or ""),
        ("Section 2 late", "Yes" if ctx.get("section2_late") else "No"),
    ]
    extra = [
        f"Form I-9 edition {I9_EDITION}. Expiration date {I9_EXPIRATION}.",
        "Section 1 attestation must be one of: citizen of the United States; noncitizen national of the United States; "
        "lawful permanent resident; or an alien authorized to work.",
        "I am aware that federal law provides for imprisonment and/or fines for false statements or use of false "
        "documents in connection with the completion of this form.",
        "Section 2 is a human examination of original documents. Uploaded photos are copies only.",
    ]
    return _draw_working_copy(
        f"Form I-9 Employment Eligibility Verification (edition {I9_EDITION})",
        rows,
        watermark=draft,
        extra_paragraphs=extra,
        signature_png=signature_png,
        footer=f"I-9 edition {I9_EDITION} · expires {I9_EXPIRATION}",
    )


def render_de4(ctx: dict[str, Any], *, draft: bool, signature_png: str | None = None) -> bytes:
    rows = [
        ("Employee name", ctx.get("legal_name") or ""),
        ("Address", ctx.get("address") or ""),
        ("SSN (last 4)", ctx.get("ssn_last4") or ""),
        ("Filing status", ctx.get("filing_status") or ""),
        ("Regular allowances", str(ctx.get("regular_allowances") or "0")),
        ("Additional allowances", str(ctx.get("additional_allowances") or "0")),
        ("Extra CA withholding", str(ctx.get("extra_withholding") or "0")),
        ("Exempt", "Yes" if ctx.get("exempt") else "No"),
        ("Signed", ctx.get("signed_at") or ("pending" if draft else "")),
    ]
    extra = [
        "California Form DE-4 is separate from federal Form W-4. Do not copy W-4 elections onto this form.",
        "Under penalties of perjury, I certify that the number of withholding allowances claimed on this certificate "
        "does not exceed the number to which I am entitled.",
    ]
    return _draw_working_copy(
        "Form DE-4 Employee's Withholding Allowance Certificate",
        rows,
        watermark=draft,
        extra_paragraphs=extra,
        signature_png=signature_png,
        footer="USIS working copy of EDD Form DE-4",
    )


def render_dd_auth(ctx: dict[str, Any], *, draft: bool, signature_png: str | None = None) -> bytes:
    rows = [
        ("Account holder", ctx.get("account_holder_name") or ""),
        ("Bank", ctx.get("bank_name") or ""),
        ("Routing (last 4)", (ctx.get("routing") or "")[-4:] if ctx.get("routing") else ""),
        ("Account (last 4)", ctx.get("account_last4") or ""),
        ("Type", ctx.get("account_type") or ""),
        ("Deposit", "100% to this account"),
        ("Signed", ctx.get("signed_at") or ("pending" if draft else "")),
    ]
    extra = [
        "I authorize the employer to initiate ACH credit entries to the account named above and to reverse any "
        "entry made in error. I may revoke this authorization in writing at any time.",
    ]
    return _draw_working_copy(
        "Direct deposit authorization",
        rows,
        watermark=draft,
        extra_paragraphs=extra,
        signature_png=signature_png,
    )


def render_notices(ctx: dict[str, Any], *, draft: bool, signature_png: str | None = None) -> bytes:
    acks = ctx.get("acks") or []
    rows = [("Employee", ctx.get("legal_name") or "")]
    for a in acks:
        rows.append((a.get("title") or a.get("key") or "notice", a.get("acknowledged_at") or "not acknowledged"))
    extra = [
        "California new-hire notices are receipts of official pamphlets. This page does not rewrite the legal text. "
        "Replace each notice template with the current Labor Commissioner / EDD PDF.",
    ]
    return _draw_working_copy(
        "California new-hire notice acknowledgments",
        rows,
        watermark=draft,
        extra_paragraphs=extra,
        signature_png=signature_png,
    )


def render_de34(ctx: dict[str, Any]) -> bytes:
    rows = [
        ("Employer", ctx.get("employer_legal_name") or ""),
        ("EDD account (masked)", ctx.get("edd_masked") or ""),
        ("FEIN (masked)", ctx.get("fein_masked") or ""),
        ("Employee name", ctx.get("legal_name") or ""),
        ("SSN", ctx.get("ssn") or ""),
        ("Start of work", ctx.get("start_of_work_date") or ""),
        ("Address", ctx.get("address") or ""),
        ("File in", "EDD e-Services for Business within 20 calendar days of start-of-work. CM does not file."),
    ]
    return _draw_working_copy(
        "DE 34 Report of New Employee(s) — worksheet",
        rows,
        watermark=False,
        extra_paragraphs=[
            "HR must file this report in EDD e-Services. Check the payroll-setup box and store the confirmation number.",
        ],
        footer=f"Generated {date.today().isoformat()}",
    )


def render_notice_placeholder(title: str) -> bytes:
    return _draw_working_copy(
        title,
        [("Status", "Placeholder — replace with the official pamphlet PDF when the agency revises it.")],
        extra_paragraphs=[
            "Do not rewrite the legal text of this notice. Download the current official PDF from the "
            "California Labor Commissioner or EDD and upload it as the form template blank.",
        ],
    )
