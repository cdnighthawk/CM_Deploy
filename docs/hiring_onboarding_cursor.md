# USIS CM — New Hire Onboarding (Employee Packet → Federal/CA Forms → Sign → Payroll Setup)

**Date:** 2026-09-05  
**Repo:** `CM_Deploy`  
**Website product:** **USIS CM** (not FinishWorks)  
**Module:** People / Hiring  
**Owner company:** US Interior Specialties — finish-work subcontractor, CA commercial + government  
**Cursor implement:** `artifacts/hiring_onboarding_implement_cursor.md`  
**Depends on:** `website_product_plan_cursor.md` §1 stack, `workflow_engine_cursor.md`, `quickbooks_desktop_web_connector_cursor.md` (do not write employees into QB in v1), `timekeeping_web_busybusy_cursor.md` (reuse `User` / `EmployeeTimeProfile`, do not invent a second employee table)

This is the **authoritative product lock** for hiring. If an older encyclopedia page says React / MUI / `src/pages/*.tsx` / “HR Employees module,” ignore it.

---

## 0. What we are building

A website hiring packet so a new employee enters personal data once. The system **fills the official forms from that data**. The employee **reviews the filled forms and signs**. HR then finishes the employer sections (especially I-9 Section 2), locks the packet, and uses a **payroll-setup export** to create the person in QuickBooks Desktop payroll and tax accounts.

USIS CM is **not** the payroll tax engine. QuickBooks Desktop Enterprise Contractor remains the accounting / payroll book of record (`quickbooks_desktop_web_connector_cursor.md`). Timekeeping remains the hours book of record. This module is the **new-hire source packet**.

```
HR creates hire + offer fields
        ↓
Tokenized public packet  /public/hire/<token>
        ↓
Employee enters data (wizard, resume later)
        ↓
System fills Form W-4, I-9 §1, CA DE-4, direct deposit, emergency contacts
        ↓
Employee reviews each generated PDF + e-signs
        ↓
HR reviews → examines original I-9 documents → signs I-9 §2
        ↓
Packet locked  →  payroll setup checklist + export for QB / EDD
        ↓
Link or create existing User  →  Time profile eligible on start date
```

---

## 1. Non-negotiable rules

- Keep xAI/Grok, ChatBot core, `aiReviewBus`, DrawingViewer, RFP, Estimating, Submittal QC, POs, Time punch math untouched.
- **Never send hire-packet PII to Grok or Local Llama.** No “AI fill my W-4,” no SSN in any AI prompt, no hire PDFs in `construction_review`.
- Staff UI = W3CRM + Bootstrap 5 + DataTables + `usis-ui.css` LAST + `window.USISUi`. No React / MUI pages.
- Public hire pages live in Flask (`public_portal.py` or a sibling public blueprint), same pattern as `/public/rfp/<token>`. Not inside the authenticated W3CRM shell.
- No Jinja2 in frontend JS. Form PDFs + invite email = Flask + Jinja2.
- Do **not** invent a second employee directory. After HR marks `ready_for_payroll`, link to existing `User` (match email, then exact legal name) or create **one** `User` row. Timekeeping `EmployeeTimeProfile` is created or updated here — not a third table of people.
- Do **not** write employees, wages, or tax elections into QuickBooks in this ticket. QB v1 is pull-only. HR copies the payroll packet into QB by hand (or a later QBWC write ticket).
- Do **not** file DE 34 / E-Verify / IRS forms electronically in v1. Generate the packet and a dated “HR must file” checklist.
- Do **not** store SSN, full bank account, or routing number on `User`, on `EmployeeTimeProfile`, or in timekeeping CSV exports. Those live only on the encrypted hire packet / tax-election records.
- Do **not** collect this packet on FinishWorks Field in v1. Field is for punch / drawings / punch list. PII belongs on the public web form.
- Do **not** treat 1099 vendors as employees. Vendors stay on `Company`.
- Workflows are data. Seed `process_key = new_hire` on the shared engine. Do not hardcode a stepper.
- In-flight packets freeze the **form-template version** (W-4 year, I-9 edition, DE-4 revision) at invite time.
- Electronic I-9 must be designed against **8 CFR 274a.2(e)–(i)** (audit trail, integrity, reproduce a complete form on demand). A typed name in a random `<input>` is not enough.
- Electronic W-4 substitute must keep IRS-required wording from Step 1(c) through Step 4(c) plus the 2026 “Exempt from withholding” block (Pub. 15-T). Do not “simplify” the W-4 into three dropdowns.
- I-9 Section 2 is **not** auto-completed from uploaded photos. Photos are a file copy only. The examiner must see original documents (or a documented DHS alternative procedure — out of v1).

---

## 2. Who uses which surface

| Person | Surface | Does |
|---|---|---|
| New hire / rehire | Public `/public/hire/<token>` (phone + desktop) | Enters data, reviews PDFs, signs |
| HR / office admin | USIS CM **People → Hiring** | Creates packet, chases incomplete, reviews, I-9 §2, export |
| Payroll admin | Same + Time → Payroll later | Uses export to set up QB employee + tax items |
| Superintendent | Not this module | Does not approve W-4s |
| Local AI / Grok | Nowhere on this module | |

Invite email From / Reply-To is a **company setting** `hire_mail_from` (seed `hr@gousis.com` — amendable; do not hardcode). BCC the same address so the office has a copy. One token per hire. Do not CC other candidates.

---

## 3. Federal + California forms in v1

Company is California. “Federal only” would leave payroll and taxes unfinished. v1 generates and stores the following.

### 3.1 Employee completes / signs (system-filled from packet data)

| Form | Role | Notes |
|---|---|---|
| **Form W-4** (current year; 2026 layout) | Federal income-tax withholding | Steps 1–5. Employee must be able to complete 2, 3, 4 and the exemption checkbox. Signature = Step 5. |
| **Form I-9 Section 1** (edition **01/20/25**, expiration **05/31/2027**) | Employment eligibility attestation | Name, address, DOB, SSN (collect — needed for payroll and EDD), email, phone, citizenship / alien-authorized-to-work attestation. Signature + date on or before day 1. |
| **Form DE-4** | California PIT withholding | Do **not** reuse W-4 elections for CA. Separate form. |
| **Direct deposit authorization** | Payroll (not a federal form) | Bank name, routing, account, checking/savings, deposit percent or dollar split (v1: one account, 100%). Optional voided-check / bank-letter upload. |
| **Emergency contacts** | Safety / HR | Two contacts. |
| **Acknowledgment of CA new-hire notices** | CA delivery duty | Employee checks “I received and can download” each notice. Store PDF copies of the official pamphlets, do not rewrite the legal text. |

### 3.2 Employer completes (staff, after employee signs)

| Form / action | Deadline | Notes |
|---|---|---|
| **Form I-9 Section 2** | Within **3 business days** of start-of-work | Document title, issuing authority, number, expiration from List A **or** List B + List C. Examiner name, title, employer address, signature, first-day date. |
| **I-9 document copies** | Same visit | Upload photos/scans of the documents examined. Copy ≠ examination. |
| **EDD Report of New Employee(s) (DE 34)** | Within **20 calendar days** of start-of-work | Generate a filled DE 34 **worksheet** + checklist item. HR files in EDD e-Services. System does not call EDD. |
| **Federal new-hire directory** | Covered by DE 34 in CA | Do not build a second federal e-file. |
| **Payroll setup in QuickBooks** | Before first check | Checklist + CSV/PDF packet. Human enters into QB. |

### 3.3 California notices the company must **give** (acknowledge + attach official PDF)

Seed as template files HR can replace when the Labor Commissioner / EDD revises them:

- Wage Theft Protection Act notice (Labor Code 2810.5) — required for non-exempt (almost every field craft).
- Paid Sick Leave notice.
- EDD SDI / Paid Family Leave pamphlets (DE 2515 / DE 2511 current revisions).
- IWC Wage Order acknowledgment (finish work is typically **Wage Order 16** — on-site construction; office staff may be Order 4. Store `wage_order` on the hire).
- Workers’ compensation time-of-hire pamphlet.
- **Workplace Know Your Rights** notice (SB 294, required for new hires starting 1 Feb 2026) — Labor Commissioner model notice.
- Sexual-harassment prevention pamphlet / policy receipt.
- Health Insurance Marketplace coverage notice (if the company offers or does not offer medical — two official variants; pick via company setting).

These are **receipts**, not tax elections. Missing them is a CA penalty even when W-4 is perfect.

### 3.4 Out of v1 (do not build)

- E-Verify / E-Verify+ case create (flag on the hire if the **project** is a federal contract that requires it; HR runs E-Verify outside CM).
- Benefits enrollment (medical / 401k / union welfare).
- Offer-letter legal drafting / e-sign of the employment contract beyond a stored PDF attachment.
- Background-check vendor, drug-screen vendor.
- I-9 remote alternative procedure / video examination.
- I-9 Supplement B reverification workflow (store the blank; do not automate).
- Form W-4P / W-4S / W-9 / 1099-NEC.
- State forms for states other than California (if they ever hire in NV/AZ, add a state pack later).
- Certified payroll, DIR, union dispatch, fringe trust enrollment.
- Push `EmployeeAdd` to QuickBooks Web Connector.
- Collecting this packet inside FinishWorks Field.
- AI-suggested withholding or “optimal W-4.”

---

## 4. Data the employee enters (single source)

One `HirePacket` of facts. Forms are **projections** of this packet, not separate typed copies the employee fills three times.

### 4.1 Identity and contact

- Legal first, middle, last, suffix — **as printed on the Social Security card**
- Preferred / badge name (this one may go on `User`)
- Date of birth
- SSN (full, encrypted)
- Personal email, mobile
- Street, city, state, ZIP (mailing = residential checkbox)
- County (optional)

### 4.2 Work eligibility (I-9 Section 1)

Exactly the four attestations on the current I-9:

1. Citizen of the United States  
2. Noncitizen national of the United States  
3. Lawful permanent resident — USCIS / A-number  
4. An alien authorized to work — A-number / Form I-94 / foreign passport + work-until date as the form requires  

Employee picks **one**. Do not invent extra statuses.

### 4.3 Federal W-4 elections (2026)

- Step 1(c) filing status: Single or Married filing separately | Married filing jointly | Head of household
- Step 2 checkbox (multiple jobs / spouse works)
- Step 3 credits amount (dollars)
- Step 4(a) other income, 4(b) deductions, 4(c) extra withholding per pay period
- Exempt-from-withholding checkbox + the required 2026 certification text
- Signature + date (Step 5)

If the employee claims exempt, hide / zero Steps 2–4 per IRS rules and show the exemption certification.

### 4.4 California DE-4 elections

Collect the current DE-4 fields (filing status, regular allowances, additional allowances, extra CA withholding, exemption claim if any). Map 1:1 onto the official DE-4 revision frozen on the packet. Do not derive DE-4 from W-4.

### 4.5 Direct deposit

- Financial institution name
- Routing number (9 digits, checksum)
- Account number
- Type: checking | savings
- Account-holder name (default legal name)
- Authorization text (ACH, revoke anytime in writing)

### 4.6 Emergency + misc. needed to stand up payroll

- Two emergency contacts (name, relation, phone)
- Federal filing / work location state (seed CA)
- Driver’s license number + state **only if** `drives_for_work` is true on the hire (field employees who run company or personal vehicles to sites)
- Optional: last company, referred-by (plain text)

Do **not** collect race / ethnicity, medical conditions, or disability in v1 (separate confidential file if legal later asks).

### 4.7 HR-only fields (not on the public form)

Set when the packet is created, editable until invite is sent, frozen after employee starts Section 1 unless HR voids and reissues:

| Field | Seed / notes |
|---|---|
| `hire_type` | `new` \| `rehire` |
| `start_of_work_date` | First day services performed for wages (EDD + I-9) |
| `job_title` | e.g. Painter, Drywall Finisher, Project Manager |
| `employment_class` | `hourly_nonexempt` (seed) \| `salary_exempt` |
| `pay_rate_display` | Optional; **do not** put on public form unless HR toggles `show_rate_on_packet` |
| `pay_frequency` | weekly (seed, matches Time) |
| `primary_project_id` | Optional home job |
| `union_status` | `nonunion` \| `union` + local name text |
| `wage_order` | `16` field / `4` office |
| `work_state` | `CA` |
| `requires_e_verify` | false unless project flag |
| `drives_for_work` | bool |
| `offer_letter_file` | optional PDF in Documents |

Pay rate may exist on `EmployeeTimeProfile` later. It is **not** printed on W-4 / I-9.

---

## 5. Public employee experience

Route: `GET /public/hire/<token>`

Look and feel: same public chrome family as the RFP vendor page (USIS tokens, not W3CRM cyan). Mobile-first. Works on a phone in a parking lot.

### 5.1 Token rules

- Unique, unguessable, 32+ bytes.
- Expires `start_of_work_date + 14 days` or 30 days from invite, whichever is later. HR can regenerate.
- After `employee_signed`, token becomes **read-only** (download own PDFs + “already submitted”).
- After HR locks the packet, token 404s except a short “packet closed, contact HR” page.
- Progress saved server-side per step so they can close the phone and resume. No local-only PII cache of SSN.

### 5.2 Wizard steps (lock this order)

1. **Welcome** — company name, start date, job title, what they will sign, link to official IRS / USCIS / EDD instructions (external). Language toggle out of v1 (English only).
2. **You** — identity + address + contact.
3. **Work eligibility** — I-9 Section 1 attestation only. Short plain-language help. Link to Lists of Acceptable Documents so they know what to **bring on day 1**. They do **not** upload List A/B/C here.
4. **Federal tax (W-4)** — official step wording on the screen. Live preview panel of the filled W-4 PDF.
5. **California tax (DE-4)** — same pattern.
6. **Pay deposit** — bank + optional voided check.
7. **Emergency + acknowledgments** — contacts + CA notice receipts (each notice opens the official PDF).
8. **Review & sign** — stacked PDFs (W-4, I-9 §1, DE-4, direct deposit, acknowledgments). Per-form attestation checkbox quoting the form’s perjury / authorization sentence. Drawn signature + typed legal name. One signature block may apply to all employee forms **only if** each form’s required certification text is checked individually first.

Cannot jump to Sign with empty required fields. Server validates again.

### 5.3 Signature capture (employee)

For each signed artifact store:

- Typed legal name (must match packet legal name, case-insensitive)
- PNG of drawn signature (or mouse)
- ISO timestamp, timezone America/Los_Angeles display
- Source IP, user-agent
- Form template version id
- Hash of the frozen PDF bytes at sign time

Show the perjury text **immediately above** the pad. Clicking Sign without the checkboxes is rejected.

If they request a paper copy, “Download signed packet” produces the frozen PDFs. Required for electronic I-9.

---

## 6. Staff experience

### 6.1 Left nav

New parent **People** (company-level, not a seventh project-details parent):

```
People
  Hiring          /people/hiring          ← default
  Directory       /people/directory       ← thin list of User + hire status; do not rebuild CRM
```

Do **not** put Hiring under Time, Settings, or a project strip. A hire is a company person, not a job file.

### 6.2 Hiring board (`/people/hiring`)

DataTables list:

`Employee | Job title | Start | Stage | W-4 | I-9 §1 | I-9 §2 | DE-4 | Deposit | Notices | Days to I-9 §2 due | Owner`

Stage chips via `USISUi.statusChip`. Filters: stage, start-week, incomplete I-9, missing deposit.

Actions: New hire, Resend invite, Void packet, Open packet.

### 6.3 Packet detail

Tabs: Overview | Employee data (masked) | Forms | I-9 Section 2 | Notices | Payroll setup | Audit.

SSN display: `***-**-1234` default. “Reveal” is a logged event (`ssn_view`) limited to `hr_admin` / `payroll_admin`.

### 6.4 I-9 Section 2 desk

Own tab, not mixed into the W-4.

- First day of employment (defaults to `start_of_work_date`)
- List A **or** List B + List C (UI prevents mixing List A with B/C)
- Seed common construction documents: U.S. passport; driver’s license + Social Security card; permanent resident card; EAD
- Fields: document title, issuing authority, document number, expiration (N/A allowed where the form allows)
- Upload copies
- Examiner (logged-in user), title, employer business name + address from company settings
- Additional information box
- Employer signature + date
- Block sign if Section 1 is unsigned or start date is empty
- Banner if today > start + 3 business days (`i9_section2_late`)

### 6.5 Payroll setup tab (the reason this module exists)

After employee_signed + I-9 §2 signed (or HR override with reason for “start-date still in future, §2 scheduled”):

Checklist (real gates, not decoration):

| Gate | Pass when |
|---|---|
| W-4 signed, current-year template | `w4.signed_at` |
| DE-4 signed | `de4.signed_at` |
| I-9 §1 signed | |
| I-9 §2 signed | or scheduled date recorded |
| Direct deposit present or “pay by check” flagged | |
| CA notices acknowledged | |
| `User` linked or created | |
| `EmployeeTimeProfile` exists, `clock_eligible` on start date | |
| DE 34 marked filed | HR checks the box + files the confirmation number |
| QB employee created | HR checks the box + optional ListID paste |

**Export payroll packet** (Documents Hub + download), Flask + Jinja2:

1. PDF bundle: signed W-4, signed DE-4, I-9 (both sections), direct-deposit authorization, notice receipts, DE 34 worksheet.
2. CSV one-row for the payroll clerk (no full SSN in the CSV filename; SSN column included because they must type it into QB — file lands in the encrypted hire folder, not the public Documents grid).

CSV columns (seed):

`legal_name, preferred_name, email, mobile, address1, city, state, zip, ssn, dob, start_of_work_date, job_title, class, work_state, w4_filing_status, w4_step2, w4_step3, w4_other_income, w4_deductions, w4_extra, w4_exempt, de4_filing_status, de4_allowances, de4_additional_allowances, de4_extra, de4_exempt, bank_name, routing, account, account_type, emergency_1, emergency_1_phone`

This CSV is the “set up payroll and taxes” deliverable. It is **not** a time-card export.

---

## 7. Workflow (`process_key = new_hire`)

Seed published definition. Labels amendable. In-flight packets freeze version.

| step_key | Actor | Exit |
|---|---|---|
| `draft` | HR | required HR fields + start date + title |
| `invite_sent` | system | email with token queued Celery |
| `employee_in_progress` | employee | any step saved |
| `employee_signed` | employee | all required employee artifacts signed |
| `hr_review` | HR queue | data looks consistent (name vs SSN card reminder — human) |
| `i9_section2` | HR / authorized examiner | Section 2 signed |
| `ready_for_payroll` | HR | User linked + export generated |
| `payroll_setup` | payroll admin | DE 34 filed checkbox + QB created checkbox |
| `closed` | system | start date reached or manual close |
| `void` | HR | reason required; token killed; do not delete artifacts |

Reject / send-back from `hr_review` returns the employee to `employee_in_progress` with a plain-text note on the public page (no legal advice).

Notify via existing SMTP + Celery + notification center. No staff chat.

---

## 8. Data model (add only what is missing)

Discover `User` first. Do not clone it.

### `HirePacket`

| Field | Notes |
|---|---|
| id | UUID |
| user_id | FK nullable until linked |
| public_token_hash | store hash, not raw token |
| token_expires_at | |
| hire_type | new / rehire |
| stage | denormalized from workflow for the list |
| workflow_instance_id | |
| start_of_work_date | |
| job_title, employment_class, union_status, wage_order, work_state | |
| drives_for_work, requires_e_verify, show_rate_on_packet | |
| primary_project_id | nullable |
| form_pack_version_id | frozen templates |
| invited_at, employee_signed_at, locked_at, voided_at | |
| created_by | |

### `HirePerson` (1:1 packet; encrypted columns)

Legal name parts, DOB, SSN ciphertext + last4, address, email, mobile, preferred name.

### `HireTaxElection`

One row per form per packet: `w4`, `de4`. JSONB `fields` matching that template version + `signed_at` + `pdf_document_id`.

### `HireI9`

Section 1 fields + attestation enum + section 2 document rows (child `HireI9Document`) + examiner + both signatures + late flag.

### `HireDirectDeposit`

Encrypted routing + account, last4 account, bank name, type, signed_at, optional voided-check file id.

### `HireEmergencyContact`

### `HireNoticeAck`

`notice_key`, template version, acknowledged_at, pdf id.

### `HireSignature`

Shared signature blob + metadata + `artifact_key`.

### `FormTemplate`

`key` (`w4`, `i9`, `de4`, `de34`, `dd_auth`, `notice_2810_5`, …), `edition`, `effective_from`, `pdf_blank_path`, `field_map` JSON (PDF AcroForm names or stamp coordinates), `is_frozen_default`.

HR replaces a template by uploading a new official blank and mapping fields. Packets already invited keep the old version.

Encryption: application-level (Fernet / app key from env). Key rotation procedure in comments. Backups of ciphertext without the key are useless — document that for IT.

Audit: every create, view-unmask, download, sign, void, export. Reuse existing audit log.

---

## 9. Form filling (how “the system fills the forms”)

1. Store the **official blank PDF** for each template under the documents templates root (company downloads from IRS / USCIS / EDD — we do not ship a redrawn official form as our IP).
2. `field_map` says which packet path writes to which AcroForm field, or which x/y stamp if the PDF is flat.
3. On every wizard save of a relevant step, rebuild a **draft** PDF (watermark DRAFT).
4. On sign, rebuild without watermark, embed signature image in the signature box, write date, hash, persist immutable bytes. Further edits require void + new packet or a dated amendment row (W-4 changes after hire are a new `HireTaxElection` version, not a rewrite).

Do not rasterize a screenshot of a web form and call it Form W-4. The artifact HR prints for an audit must be recognizable as that year’s official form.

I-9 generated PDF must show edition `01/20/25` and expiration `05/31/2027` on current packets.

---

## 10. Security and retention

| Rule | Detail |
|---|---|
| Transport | HTTPS only on public hire routes |
| At rest | SSN, DOB, bank routing/account encrypted |
| Access | `hr_admin`, `payroll_admin` full; other staff see name + stage + start date only |
| AI | Blocked. No mode, no button, no bus event |
| Retention I-9 | 3 years after hire **or** 1 year after termination, whichever later |
| Retention W-4 / DE-4 | 4 years after the tax year they last used (IRS / EDD practice) — do not auto-purge in v1; add a retention report only |
| Separation | I-9 packet should be downloadable as its own file set so it can be produced without handing an auditor the W-4 |
| Token | Hash at rest; raw token only in the email |

---

## 11. Integrations (reuse, do not rebuild)

| Existing | How hiring uses it |
|---|---|
| `User` | Link / create after HR review |
| `EmployeeTimeProfile` | Create on link; `clock_eligible` false until `start_of_work_date` |
| QuickBooks WC | No write. Optional paste of QB ListID on the payroll-setup tab so the later pull matches |
| Documents Hub | Signed PDFs + exports live here, **HR-restricted folder** `hr/hires/<packet_id>/` — not on the project file tree |
| SMTP + Celery | Invite, reminder 48h before start if unsigned, I-9 §2 due reminder to HR |
| Audit log | All PII views and signs |
| Workflow engine | `new_hire` |
| Public portal | Token page pattern from RFP |
| Field app | Out. After `User` exists and start date hits, they log into FinishWorks Field with the normal account |

---

## 12. Company settings to seed

```
hire_mail_from = hr@gousis.com
hire_mail_reply_to = hr@gousis.com
employer_legal_name
employer_address
employer_fein          # used on DE 34 worksheet only; restrict reveal
edd_account_number     # eight-digit; restrict reveal
i9_section2_business_name
i9_section2_address
marketplace_notice = offers_health | does_not_offer_health
default_wage_order = 16
default_pay_frequency = weekly
```

Do not put FEIN on the public employee page.

---

## 13. Success is

A painter can finish the packet on a phone the night before day one. The office prints a signed W-4, DE-4, and I-9 that an auditor recognizes. HR ticks DE 34 + QB employee created. Timekeeping can punch them on the start date. No SSN ever lands in ChatBot, Grok, a project Documents folder, or a time-card CSV.
