# Mobile apps

Status: complete
Sage CM module: Companion products
Official help: https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm

## Purpose

The Sage Construction Management **mobile app** is the field client for alerts, to-dos, schedule edits, correspondence, photos, daily logs, work orders, QC/Safety, limited contract/procurement, and time/expenses. iOS help is the official capability matrix (Read / Edit / Add / Delete / email). Sage AI OCR can turn photos/PDFs into **bills** and **miscellaneous expenses**.

## Where it lives

- **Apple App Store** — search “Sage Construction Management”; iOS **11.0 or higher**.
- Same Sage CM cloud data as the web app (not a separate database).
- Android store listing is **not confirmed** on the Apple overview page (help title is Apple iPhones and iPads; intro says “learn more about the mobile apps”).
- **Not** the USIS Expo field app (`mobile/` in this repo).

## Who uses it

- Superintendents and field crews: daily logs, photos, punchlist, SHA, clock in/out, timecards.
- PMs: RFIs, issues, journals, WO headers/items, comply notices, workflow approvals.
- Accounting field: bills and misc expenses via OCR.
- Permissions still follow the user’s Sage **security role**; the matrix is what the **app can do**, not a grant of extra rights.

## Prerequisites

- iOS 11.0+ device; App Store install.
- Sage CM user login (fields **not listed** on the overview — treat username/password or SSO as **not confirmed**).
- Photos: mobile max **100 MB** per file, **10** photos at a time (stricter than web 500 MB / 48 files).
- OCR bills/expenses: Sage AI on mobile (starred rows in the matrix).

## What the user fills out

The app does not add a new data model. Users fill the **same feature fields** as web, constrained by R/E/A/D:

### User and directory

| Module/Feature | R | E | A | D | Email | Notes |
|---|---|---|---|---|---|---|
| User profile | Yes | Yes | | | | |
| Companies | Yes | | | | | |
| Contacts | Yes | Yes | Yes | | | |
| Lead - Add Wizard | | | Yes | | | |
| Lead - Title and address | Yes | Yes | | | | |
| Lead - Directory | Yes | | Yes | Yes | | |
| Project - Title and address | Yes | Yes | | | | |
| Project directory - Listing | Yes | | Yes | Yes | | |
| Project directory - Company overview status | Yes | | | | | |

### Alerts, to-dos, schedule

| Module/Feature | R | E | A | D | Email |
|---|---|---|---|---|---|
| Alerts | Yes | | | | |
| Workflow alerts and approvals | Yes | Yes | | | |
| General and project to-dos | Yes | Yes | Yes | Yes | |
| Schedules and tasks | Yes | Yes | | | |

### Drawings / specs / correspondence

| Module/Feature | R | E | A | D | Email |
|---|---|---|---|---|---|
| Drawings | Yes | | | | |
| Specifications | Yes | | | | |
| Issues | Yes | Yes | Yes | Yes | Yes |
| Journals | Yes | Yes | Yes | Yes | Yes |
| RFI | Yes | Yes | Yes | Yes | Originator: No; Respondent: Yes |
| Submittals | Yes | | | | Originator: No; Respondent: Yes |

### Documentation (this doc set)

| Module/Feature | R | E | A | D | Email | Notes |
|---|---|---|---|---|---|---|
| Photos | Yes | Yes | Yes | Yes | | Max 100 MB |
| Daily logs | Yes | Yes | Yes | Yes | | |
| Work orders | Yes | Yes (items, headers, reviewer comments) | Yes (items, headers) | Yes (items) | | |

**Not on the matrix:** Meetings, Owner Items.

### QC and safety

| Module/Feature | R | E | A | D | Email |
|---|---|---|---|---|---|
| Checklists | Yes | Yes | Yes | Yes | |
| Comply notices | Yes | Yes | Yes | Yes | Yes |
| Permits | Yes | Yes | Yes | Yes | |
| Punchlist items | Yes | Yes | Yes | Yes | Yes |
| Test and inspections | Yes | Yes | Yes | | |
| Site hazard assessments | Yes | Yes | Yes | Yes | |
| Safety incidents | Yes | Yes | Yes | Yes | |
| Safety meetings | Yes | Yes | Yes | Yes | |

### Contract / procurement / time

| Module/Feature | R | E | A | D | Email | Notes |
|---|---|---|---|---|---|---|
| Prime contract | Yes | | | | | |
| CPR | Yes | Yes | Yes | | | |
| CO | Yes | | | | | |
| Prime invoices | Yes | | | | | |
| PO | Yes | Yes | Yes | Yes | Yes | |
| PO CO | Yes | Yes | Yes | Yes | | |
| Bills | Yes | Yes | Yes* | Yes | | * Sage AI OCR |
| Subcontract | Yes | | | | | |
| SCO | Yes | | | | | |
| Subcontract invoices | Yes | | | | | |
| Labor timecards | Yes | Yes | Yes | Yes | | |
| Labor clock in / out | | | Yes | | | Add only |
| Equipment timecards | Yes | Yes | Yes | Yes | | |
| Miscellaneous expenses | Yes | Yes | Yes | Yes | | * OCR |

Create/edit field tables for each tool are in the sibling markdown files — mobile uses those same fields.

## What Sage CM saves

- **Header / lines / files:** Same persistence as web for each feature (see those tool docs).
- **System-generated values:** Same numbers/dates as web.
- **Files / attachments:** Photo size cap 100 MB / 10 at a time; OCR creates bill or misc-expense records from images/PDFs.
- **Audit / workflow fields:** Workflow alerts editable; clock-in/out is Add-only punches.

## Statuses and lifecycle

App login → work online against the same statuses as web (WO Open/Approved, punchlist Open/Closed, sample Pending/Compliance, task % complete, etc.). Clock in/out creates labor clock events (web Time and expenses module).

## Dates that drive alerts

Mobile **Alerts** is read-only against the same Home Alerts calendar (see `AlertsCalendar_All.htm`). No extra mobile-only alert dates in help.

## Relationships

- **Upstream:** Sage CM cloud; security roles; Feature Settings catalogs.
- **Downstream:** Same records PMs see on web; OCR bills/expenses; punchlist/comply email from the device.
- **USIS mobile:** Expo app for daily reports, field photos, time punches, daily pretask — **not** this Sage app.

## Reports and exports

- Email from Issues, Journals, RFI (respondent), Submittals (respondent), Comply notices, Punchlist items, POs.
- No separate “mobile report” catalog in the overview.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Sage CM iOS app | none | none |
| Field daily report | `daily_reports` / field API | partial (USIS app, not Sage) |
| Field photos | `field_photos` | partial |
| Time clock | `time_entries`, `time_punches` | implemented (USIS geofence/photos; not Sage labor clock-in) |
| Daily pretask | `daily_pretasks`; `mobile/SAFETY.md` | implemented (USIS-only) |
| Sage punchlist/WO/SHA on device | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos.htm (mobile photo limits)
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/field_ops.py`
  - `backend/app/models/safety.py`
  - `mobile/SAFETY.md`
  - `mobile/src/api/safety.ts`
