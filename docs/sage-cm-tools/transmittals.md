# Transmittals

Status: complete
Sage CM module: Correspondence / Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Correspondence/Transmittals/TransmittalsOverview.htm

## Purpose

A transmittal is a formal cover document that records what was sent from one party to another (drawings, submittals, change notices, progress invoices) and why (Transmitted For). Sage stores **From** and **To** as directory companies/contacts (plus address type), a due date for the calendar, and **transmittal items** (item #, description, qty, return qty, unit, transmitted-for). Wizards can build transmittals from groups of submittals or drawings. There is no TeamLink respondent-response grid like RFIs/submittals.

## Where it lives

- Lead or Project Home → Documentation → Transmittals → Actions → Add Manually (official add path). Also listed under Correspondence in the resource center, numbering, and alerts.
- Wizards: create transmittals for groups of submittals or drawings.
- Actions: Email, Print/share, Copy to other leads/projects, multiple copies on the same lead/project.
- Correspondence Calendar / Alerts: Due Date.
- Mobile / TeamLink: print/email/share; Grant Access on linked files if emailed with portal files. No respondent comment workflow in official transmittal help.

## Who uses it

Correspondence-capable roles (including Estimator). From is typically your firm; To is the receiving company.

## Prerequisites

- From and To companies on the project directory.
- Feature Settings → Correspondence: Transmittal Types; Transmittal Sender options; Transmitted For options.
- Default numbering for Transmittals.

## What the user fills out

### Step 1 — General

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead / Project number | Yes | Context | Prefilled, editable |
| Issue Date | Yes | Date | Prefilled |
| Transmittal # | Yes | Text | Prefilled from numbering |
| Type | No | Lookup | Filter/sort; admin Transmittal Types (Changes, Contract, Mockups, Progress Invoice, Samples, Shop Drawings, Schedule, …) |
| Sender | No | Lookup | Admin Transmittal Sender options |
| Due Date | No | Date | Correspondence calendar + alert |
| Subject | Yes | Text | Brief subject |
| From Company | Yes | Lookup | Directory; typically your firm |
| From Contact | No | Lookup | |
| From Address Type | No | Lookup | |
| To Company | Yes | Lookup | Directory |
| To Contact | No | Lookup | |
| To Address Type | No | Lookup | |
| Comments / Remarks | No | Text | |
| Prime contract # | No | Lookup/text | References |
| CPR / CO # | No | Lookup/text | |
| Subcontract # | No | Lookup/text | |
| SCO # | No | Lookup/text | |
| Drawing | No | Lookup/text | |
| Location | No | Text | |
| Spec. Section | No | Text | |
| Other | No | Text | |

### Step 2 — Transmittal items

Skip if you will import drawings/submittals after create.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text | Prefilled, editable |
| Description | Yes | Text | |
| Quantity | No | Number | |
| Return Quantity | No | Number | |
| Unit | No | Text | |
| Transmitted For | No | Lookup | Admin list (e.g. approval, review — exact option names not listed on add page) |

### Step 3 — Files

Same Linked Files pattern: local upload (48 / 500 MB, background), Link Existing (Drawings & Specs, Photos, All Other Records). Skip and Finish allowed.

### Email / print

Template: Transmittal. Recipients/CC, Grant Access on linked files, Email Upload Attachments (email only).

## What Sage CM saves

- Header record: transmittal (number, issue date, type, sender, due date, subject, From company/contact/address type, To company/contact/address type, comments, references).
- Line / child records: transmittal items (item #, description, qty, return qty, unit, transmitted for); copies to other projects; wizard-created item rows from drawings/submittals.
- System-generated values: Transmittal #; default issue date today.
- Files / attachments: Linked Files.
- Audit / workflow fields: no Sequential/Parallel response workflow; no Closed status called out on official overview (due date drops from calendar when passed/handled — close behavior not confirmed in help).

## Statuses and lifecycle

Issued/sent via email or print. Copy creates additional transmittals. Submittal/drawing wizards produce a transmittal that points at those records. No TeamLink response loop.

## Dates that drive alerts

Due Date only (official alerts table).

## Relationships

- Upstream: directory, types/sender/transmitted-for, drawings, submittals.
- Downstream: Email/print; copies; Documentation vs Correspondence navigation (same record family).

## Reports and exports

- Transmittal detail report / email template.
- Log reports.
- PDF/Word print and Save to Linked Files (same pattern as journals).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Transmittal header | none | none |
| Transmittal items | none | none |
| Submittal “transmit to AE” | `POST /submittals/<id>/transmit-to-ae`; `public_token` | stub — not a Sage transmittal document |
| Flask stamp/transmittal PDF note | `docs/submittal_qc_process_cursor.md` | stub |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Transmittals/TransmittalsOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/Correspondence/Transmittals/TransmittalsAddManually.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_Correspondence_TransmittalTypes.htm
- https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local: `backend/app/api/submittals_bp.py` (transmit-to-ae only)
