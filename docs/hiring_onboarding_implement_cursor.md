# Cursor Ticket — Implement USIS CM Hiring / New-Hire Packet

**Repo:** `CM_Deploy`  
**Product:** **USIS CM** (not FinishWorks)  
**Date:** 2026-09-05  
**Status:** Implement this ticket.  
**Product rules:** `artifacts/hiring_onboarding_cursor.md` — if this file and that file conflict on behavior, **that file wins**. If either file says React / MUI / `src/pages/*.tsx`, **ignore it**.

You are adding **People → Hiring** on the staff website plus a public token packet at `/public/hire/<token>`. Do not rebuild RFP, Time, ChatBot, DrawingViewer, or the field app.

---

## 0. Read first, then search the repo

Read, in this order:

1. **This file** (what to type, in what order)
2. `artifacts/hiring_onboarding_cursor.md` (forms, fields, security, workflow)
3. `artifacts/website_product_plan_cursor.md` §1 stack + new §4.14
4. `artifacts/workflow_engine_cursor.md` (`process_key = new_hire`)
5. `artifacts/quickbooks_desktop_web_connector_cursor.md` (no employee write; no SSN on `User`)
6. `artifacts/timekeeping_web_busybusy_cursor.md` (`User` + `EmployeeTimeProfile` only)
7. `artifacts/ui_consistency_modernization_cursor.md` (tokens, pin `usis-ui.css` LAST)
8. Public vendor pattern: existing `public_portal.py` / `/public/rfp/<token>`

Then **search CM_Deploy** before creating files.

```
User Employee employee
EmployeeTimeProfile
public_portal /public/rfp
DOCUMENT_ROOT documents
workflow process_key
deznav menu sidebar
usis-ui.js USISUi DataTables
Celery smtp send_email
Company settings
qb ListID
```

Likely homes (use what exists; do not invent a parallel tree):

| Layer | Hunt here |
|---|---|
| Models | `backend/app/models*.py` |
| Blueprints | `backend/app/**/*.py` — add `/api/hires` + public hire routes next to RFP public |
| Public HTML | Flask templates next to public RFP, not gulp auth chrome |
| Staff HTML | `gulp/src/**` construction / includes |
| Left nav | menu table or `deznav` include |
| JS | `gulp/src/assets/js/usis-*.js` |
| CSS | `gulp/src/assets/css/usis-ui.css` pinned LAST |
| PDF / email | Flask + Jinja2 + whatever PDF library the repo already uses (`pypdf`, `pdfrw`, `reportlab`, WeasyPrint). Prefer filling AcroForm on official blanks. |
| Tests | existing pytest folder |

Edit **src** and copy the same HTML/JS into **dist** only if this repo already patches dist HTML. Do **not** `gulp-clean` dist.

---

## 1. Hard rules

- Keep xAI/Grok, ChatBot core, `aiReviewBus`, DrawingViewer canvas untouched. **Zero hire PII in any AI payload.**
- Staff UI = W3CRM + Bootstrap 5 + DataTables + `window.USISUi`. No React, MUI, DataGrid, Tailwind kit.
- Pin `usis-ui.css` LAST. Primary `#1F4E5F`. Canvas `#F4F6F8`. Do not use AI purple on HR chrome.
- Status chips = `USISUi.statusChip`. Empty = `USISUi.emptyState`.
- No Jinja2 in frontend JS.
- Do not invent a second people table. Link / create `User`. Time profile = `EmployeeTimeProfile`.
- Do not store SSN or bank numbers on `User` or on timekeeping.
- Do not QBWC `EmployeeAdd`. Do not E-Verify API. Do not EDD e-Services API.
- Do not build this wizard in FinishWorks Field.
- Do not treat vendors / 1099 as hires.
- Workflows are data. Seed `process_key = new_hire`. Freeze definition + form-pack version on the packet at invite.
- I-9 Section 2 is a human examination. Uploaded photos are copies only.
- Public token hashed at rest.

---

## 2. Chrome to add (only this)

### Left nav — one new parent

**People**

- Hiring `/people/hiring` (default)
- Directory `/people/directory`

If the sidebar is a menu table, insert rows there. Do not fork `deznav` CSS. Do **not** add a seventh project-details parent.

### Public

`/public/hire/<token>` — Flask public chrome (RFP cousin). English. Mobile first.

---

## 3. Build in this order (shippable slices)

One PR is fine if reviewable. Do not start at Directory polish before packets sign.

### Slice 0 — Discover

Map existing `User`, any employee profile, `public_portal.py`, document storage, workflow register, company settings, PDF helper, encryption utilities.

Write a short `HIRE_MAPPING.md` in the repo only if `API_FIELD.md` style mapping files already exist; otherwise put the mapping comment at the top of the hire blueprint. Do not create models that duplicate `User`.

### Slice 1 — Models + encryption + form templates

Add the tables in the product brief §8.

- App-level encryption helper for SSN, DOB, routing, account. Last4 stored in the clear for UI.
- `FormTemplate` rows for: `w4_2026`, `i9_01-20-25`, `de4_current`, `de34_current`, `dd_auth`, plus notice keys in product brief §3.3.
- Official blank PDFs: put **placeholders** under the templates directory and document “replace with the downloaded IRS/USCIS/EDD PDF.” Do not invent a look-alike official form. If you cannot legally vendor the binary, generate using a clearly labeled **USIS working copy** header plus the IRS-required W-4 step text, and keep a `uses_official_blank = false` flag so HR can swap later.

Seed workflow definition `new_hire` with the steps in product brief §7.

Unit tests: encrypt/decrypt roundtrip; last4 derivation; token hash.

### Slice 2 — Staff create + invite

`POST /api/hires` — HR fields only (title, start date, class, email to invite).

`POST /api/hires/<id>/invite` — generate token, Celery email from `hire_mail_from`, stage `invite_sent`.

Email Jinja2: company name, job title, start date, button to `/public/hire/<token>`, what to bring on day 1 (original I-9 documents). No SSN in the email.

Staff list page `/people/hiring` DataTables.

### Slice 3 — Public wizard

`GET /public/hire/<token>` + JSON APIs scoped by token (not cookie auth).

Steps in product brief §5.2. Save per step. Validate SSN format (AAA-GG-SSSS, reject 000 / 666 / 9xx issuance patterns loosely — do not call SSA). Routing checksum.

Do not ask for I-9 List A/B/C uploads on the public form.

Resume later = same token. Rate-limit POST.

### Slice 4 — Fill PDFs + draft preview

On save of W-4 / I-9 §1 / DE-4 / deposit, render draft PDF. Public preview = embed or download draft.

Field map covered by tests: legal name, address, SSN last-four at minimum, filing status, I-9 attestation checkbox.

I-9 PDF must carry edition **01/20/25** and expiration **05/31/2027**.

### Slice 5 — Employee sign

Signature pad + typed name + per-form certification checkboxes + freeze PDFs + `HireSignature` rows + stage `employee_signed`.

Reject name mismatch. Persist IP / UA / hash.

`GET` after sign = read-only downloads.

### Slice 6 — HR review + I-9 Section 2

Packet detail tabs. Masked SSN with logged reveal.

Section 2 UI: List A xor (B+C). Common document presets. Examiner = current user. Late banner. Copies upload into `hr/hires/<id>/i9/`.

Stage `i9_section2` → `ready_for_payroll` when signed.

Reminder Celery: if start date is in 2 days and §1 unsigned → employee email; if start+2 business days and §2 unsigned → HR email.

### Slice 7 — Link User + Time profile + payroll export

`POST /api/hires/<id>/link-user`

Match email, then legal first+last. If none, create `User` with personal email, preferred name, **no SSN column**. Do not auto-email a password until HR clicks “Send login.”

Create / update `EmployeeTimeProfile`. `clock_eligible` false while `now < start_of_work_date`.

Payroll setup tab + checkboxes (DE 34 filed, QB created, optional ListID).

`GET /api/hires/<id>/payroll-packet.zip` — signed PDFs + DE 34 worksheet + restricted CSV. Store under `hr/hires/<id>/` with the same RBAC as reveal-SSN. Do not attach this zip to a project Documents folder.

### Slice 8 — Directory + audit polish

`/people/directory` — DataTable of `User` with hire stage if any, clock eligible, email. No bank column. No SSN.

Audit events: invite, save, sign, reveal, download packet, void, link-user.

Void: reason, kill token, keep files.

---

## 4. API sketch (rename to repo conventions)

Staff (auth + HR role):

```
GET    /api/hires
POST   /api/hires
GET    /api/hires/<id>
PATCH  /api/hires/<id>
POST   /api/hires/<id>/invite
POST   /api/hires/<id>/resend
POST   /api/hires/<id>/void
POST   /api/hires/<id>/i9/section2
POST   /api/hires/<id>/link-user
POST   /api/hires/<id>/send-login
POST   /api/hires/<id>/payroll-flags
GET    /api/hires/<id>/payroll-packet
GET    /api/hires/<id>/audit
```

Public (token):

```
GET    /api/public/hire/<token>
PATCH  /api/public/hire/<token>          # step payload
GET    /api/public/hire/<token>/preview/<form_key>
POST   /api/public/hire/<token>/sign
GET    /api/public/hire/<token>/packet    # after sign
```

Never accept `user_id`, pay rate, or FEIN from the public API.

---

## 5. Tests that must exist

- Token guess / expired / voided → 404
- Public API cannot set `start_of_work_date` or I-9 Section 2
- W-4 exempt path zeros steps 2–4
- DE-4 stored even when W-4 is exempt
- I-9 Section 2 rejects List A + List B together
- Signature without certification checkboxes fails
- Encrypted SSN not present in audit `details` JSON
- Payroll CSV is 403 for a non-HR user
- Link-user does not duplicate `User` on second click
- Time profile not clock-eligible before start date
- Workflow instance freezes definition version at invite

---

## 6. Out of this ticket

E-Verify, benefits, field-app packet, QB employee write, multi-state withholding packs, background checks, offer-letter editor, union dispatch, AI anything, People analytics dashboard.

---

## 7. Done when

HR can invite a painter, the painter can finish and sign on a phone, HR can complete I-9 Section 2, download one payroll zip, link the `User`, and Time will let them punch on the start date — without a second employee table and without SSN in ChatBot or project files.
