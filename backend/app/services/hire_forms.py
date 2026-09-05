"""Form template keys, CA notice list, and default field maps.

Official IRS / USCIS / EDD PDFs are not vendored. Working-copy PDFs are
generated at runtime and flagged ``uses_official_blank = false`` so HR can
swap in downloaded blanks later.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import select

from ..extensions import db
from ..models.hiring import FormTemplate

FORM_PACK_VERSION = "2026.1"

W4_KEY = "w4_2026"
I9_KEY = "i9_01-20-25"
DE4_KEY = "de4_current"
DE34_KEY = "de34_current"
DD_AUTH_KEY = "dd_auth"

I9_EDITION = "01/20/25"
I9_EXPIRATION = "05/31/2027"

NOTICE_KEYS: tuple[tuple[str, str], ...] = (
    ("notice_2810_5", "Wage Theft Protection Act notice (Labor Code 2810.5)"),
    ("notice_paid_sick", "Paid Sick Leave notice"),
    ("notice_de2515", "EDD SDI pamphlet (DE 2515)"),
    ("notice_de2511", "EDD Paid Family Leave pamphlet (DE 2511)"),
    ("notice_wage_order", "IWC Wage Order acknowledgment"),
    ("notice_workers_comp", "Workers' compensation time-of-hire pamphlet"),
    ("notice_know_your_rights", "Workplace Know Your Rights notice (SB 294)"),
    ("notice_harassment", "Sexual-harassment prevention pamphlet / policy receipt"),
    ("notice_marketplace", "Health Insurance Marketplace coverage notice"),
)

DEFAULT_SETTINGS: dict[str, tuple[str, bool]] = {
    "hire_mail_from": ("hr@gousis.com", False),
    "hire_mail_reply_to": ("hr@gousis.com", False),
    "employer_legal_name": ("US Interior Specialties", False),
    "employer_address": ("", False),
    "employer_fein": ("", True),
    "edd_account_number": ("", True),
    "i9_section2_business_name": ("US Interior Specialties", False),
    "i9_section2_address": ("", False),
    "marketplace_notice": ("does_not_offer_health", False),
    "default_wage_order": ("16", False),
    "default_pay_frequency": ("weekly", False),
}

W4_FIELD_MAP: dict[str, str] = {
    "legal_first": "first_name",
    "legal_middle": "middle_name",
    "legal_last": "last_name",
    "address1": "address",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "ssn_last4": "ssn_last4",
    "filing_status": "filing_status",
    "step2": "step2_multiple_jobs",
    "step3": "step3_credits",
    "step4a": "other_income",
    "step4b": "deductions",
    "step4c": "extra_withholding",
    "exempt": "exempt",
}

I9_FIELD_MAP: dict[str, str] = {
    "legal_last": "last_name",
    "legal_first": "first_name",
    "legal_middle": "middle_initial",
    "address1": "address",
    "city": "city",
    "state": "state",
    "zip": "zip",
    "dob": "date_of_birth",
    "ssn_last4": "ssn_last4",
    "email": "email",
    "mobile": "telephone",
    "attestation": "citizenship_attestation",
}

DE4_FIELD_MAP: dict[str, str] = {
    "legal_first": "first_name",
    "legal_last": "last_name",
    "address1": "address",
    "ssn_last4": "ssn_last4",
    "filing_status": "filing_status",
    "regular_allowances": "regular_allowances",
    "additional_allowances": "additional_allowances",
    "extra_withholding": "extra_withholding",
    "exempt": "exempt",
}

CERT_TEXT: dict[str, str] = {
    "w4": (
        "Under penalties of perjury, I declare that this certificate, to the best of my knowledge "
        "and belief, is true, correct, and complete."
    ),
    "i9": (
        "I am aware that federal law provides for imprisonment and/or fines for false statements "
        "or use of false documents in connection with the completion of this form. I attest, under "
        "penalty of perjury, that I have selected the correct citizenship or immigration status."
    ),
    "de4": (
        "Under penalties of perjury, I certify that the number of withholding allowances claimed "
        "on this certificate does not exceed the number to which I am entitled."
    ),
    "dd_auth": (
        "I authorize US Interior Specialties to deposit my net pay to the account identified above "
        "and to reverse any entry made in error. I may revoke this authorization in writing at any time."
    ),
    "notices": (
        "I received each California new-hire notice listed and can download the official pamphlet PDFs."
    ),
}

W4_EXEMPT_TEXT = (
    "I claim exemption from withholding for 2026, and I certify that I meet both of the following "
    "conditions for exemption: Last year I had a right to a refund of all federal income tax withheld "
    "because I had no tax liability, AND this year I expect a refund of all federal income tax withheld "
    "because I expect to have no tax liability. If you meet both conditions, write \"Exempt\" in the "
    "space below Step 4(c) on the official Form W-4. See Pub. 15-T."
)

W4_STEP_WORDING: dict[str, str] = {
    "step1c": (
        "Step 1(c). Check the box for your filing status. You can check “Head of household” only "
        "if you qualify to file as head of household. Check “Married filing jointly” if you are "
        "married and you and your spouse both work, or you have more than one job. Complete Steps "
        "2–4 ONLY if they apply to you; otherwise, skip to Step 5."
    ),
    "step2": (
        "Step 2. Complete this step if you (1) hold more than one job at a time, or (2) are married "
        "filing jointly and your spouse also works. The correct amount of withholding depends on "
        "income earned from all of these jobs. Check this box if there are only two jobs total."
    ),
    "step3": (
        "Step 3. If your income will be $200,000 or less ($400,000 or less if married filing jointly), "
        "multiply the number of qualifying children under age 17 by $2,000; multiply the number of "
        "other dependents by $500; add other credits; enter the total."
    ),
    "step4a": (
        "Step 4(a). If you want tax withheld for other income you expect this year that won’t have "
        "withholding, enter the amount of other income here. This may include interest, dividends, "
        "and retirement income."
    ),
    "step4b": (
        "Step 4(b). If you expect to claim deductions other than the standard deduction and want to "
        "reduce your withholding, use the Deductions Worksheet on page 3 of Form W-4 and enter the "
        "result here."
    ),
    "step4c": (
        "Step 4(c). Enter any additional tax you want withheld each pay period."
    ),
    "step5": (
        "Step 5. Sign here. Under penalties of perjury, I declare that this certificate, to the best "
        "of my knowledge and belief, is true, correct, and complete."
    ),
}

PAYROLL_GATE_LABELS: dict[str, str] = {
    "w4_signed": "W-4 signed (current-year template)",
    "de4_signed": "DE-4 signed",
    "i9_section1_signed": "I-9 Section 1 signed",
    "i9_section2_signed": "I-9 Section 2 signed (or scheduled)",
    "deposit": "Direct deposit on file or pay by check",
    "notices": "California notices acknowledged",
    "user_linked": "User linked or created",
    "time_profile": "Time profile exists",
    "clock_eligible_on_start": "Clock eligible on start date",
    "de34_filed": "DE 34 marked filed",
    "qb_created": "QB employee created",
}

I9_LIST_PRESETS: list[dict[str, Any]] = [
    {
        "key": "us_passport",
        "mode": "A",
        "title": "U.S. Passport",
        "authority": "U.S. Department of State",
        "lists": ["A"],
    },
    {
        "key": "dl_ssn",
        "mode": "BC",
        "title": "Driver's license + Social Security card",
        "authority": "State DMV / SSA",
        "lists": ["B", "C"],
        "b_title": "Driver's license issued by a State",
        "b_authority": "State DMV",
        "c_title": "Social Security Account Number card",
        "c_authority": "Social Security Administration",
    },
    {
        "key": "prc",
        "mode": "A",
        "title": "Permanent Resident Card (Form I-551)",
        "authority": "USCIS / DHS",
        "lists": ["A"],
    },
    {
        "key": "ead",
        "mode": "A",
        "title": "Employment Authorization Document (Form I-766)",
        "authority": "USCIS / DHS",
        "lists": ["A"],
    },
]


def _upsert_template(
    *,
    key: str,
    edition: str,
    title: str,
    field_map: dict[str, str] | None,
    effective_from: date | None = None,
    notes: str | None = None,
) -> FormTemplate:
    row = db.session.scalar(
        select(FormTemplate).where(FormTemplate.key == key, FormTemplate.edition == edition)
    )
    if row is None:
        row = FormTemplate(key=key, edition=edition)
        db.session.add(row)
    row.title = title
    row.field_map = field_map
    row.effective_from = effective_from
    row.is_frozen_default = True
    row.uses_official_blank = False
    row.notes = notes or (
        "USIS working copy. Replace pdf_blank_path with the official IRS/USCIS/EDD download "
        "and set uses_official_blank = true. Packets already invited keep this edition."
    )
    db.session.flush()
    return row


def ensure_form_templates() -> dict[str, FormTemplate]:
    out: dict[str, FormTemplate] = {}
    out[W4_KEY] = _upsert_template(
        key=W4_KEY,
        edition="2026",
        title="Form W-4 (2026)",
        field_map=W4_FIELD_MAP,
        effective_from=date(2026, 1, 1),
    )
    out[I9_KEY] = _upsert_template(
        key=I9_KEY,
        edition=I9_EDITION,
        title=f"Form I-9 (edition {I9_EDITION}, exp {I9_EXPIRATION})",
        field_map=I9_FIELD_MAP,
        effective_from=date(2025, 1, 20),
    )
    out[DE4_KEY] = _upsert_template(
        key=DE4_KEY,
        edition="current",
        title="Form DE-4 Employee's Withholding Allowance Certificate",
        field_map=DE4_FIELD_MAP,
    )
    out[DE34_KEY] = _upsert_template(
        key=DE34_KEY,
        edition="current",
        title="DE 34 Report of New Employee(s) worksheet",
        field_map={"legal_name": "employee_name", "ssn_last4": "ssn_last4", "start": "start_date"},
    )
    out[DD_AUTH_KEY] = _upsert_template(
        key=DD_AUTH_KEY,
        edition="v1",
        title="Direct deposit authorization",
        field_map={"bank_name": "bank_name", "account_type": "account_type"},
    )
    for key, title in NOTICE_KEYS:
        out[key] = _upsert_template(
            key=key,
            edition="placeholder",
            title=title,
            field_map=None,
            notes="Placeholder. Replace with the current Labor Commissioner / EDD official PDF.",
        )
    db.session.flush()
    return out


def default_template_ids() -> dict[str, str]:
    rows = ensure_form_templates()
    return {k: str(v.id) for k, v in rows.items()}
