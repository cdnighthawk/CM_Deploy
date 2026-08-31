# Permits

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/Permits/PermitsOverview.htm

## Purpose

Permits tracks permit **applications** and issued permits per project, including who pulled the permit, the issuing agency/organization, application vs permit numbers, expiration, and status. Building-department contacts can be stored on the record for follow-up without adding the agency to the project directory.

## Where it lives

- **Project Home** → Quality Control / QC and Safety → **Permits**.
- Add wizard: general permit information → linked files.
- **Quality Control Calendar:** permit **Expire date**.
- **Mobile:** Permits R, E, A, D.
- **Team Open Items:** Permits are **not** in the QC open-items table.

## Who uses it

- GC or subcontractor **Pulled By** company/contact (must be in the project directory).
- Issuing agency/organization: existing Contact Management agency **or** typed new agency/contact (directory not required).
- Office staff update Status / Status Date and expiration for alerts.

## Prerequisites

- Project; Pulled By company in the **project directory**.
- **Permit Type** list reviewed — **required** on add (Settings → Feature Settings → QC & Safety). Examples in help: plumbing, electrical.
- **Permit Status** list reviewed — optional field at the bottom of the form (same Feature Settings).

## What the user fills out

### Header (Actions → Add Manually, step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | |
| Prime Contract # | No | Prime contract | |
| Type | Yes | Dropdown | Feature Settings → QC & Safety (e.g. plumbing, electrical) |
| Subject | Yes | Text | |
| Application # | No | Text | Issued by building agency at start of plan review |
| Application Date | No | Date | |
| Permit # | No | Text | Issued permit number |
| Permit Date | No | Date | |
| Expire Date | No | Date | QC Calendar / Home Alerts |
| Pulled By Company | Yes (help: select) | Directory company | Usually GC or sub performing the work |
| Pulled By Contact | Yes (help: select) | Directory contact | |
| Issued By | No | Choice | Select Existing Agency in Contact Management **or** Enter New Agency/Organization and Contact |
| Issued By agency/org + contact | If entering | Text / contact | New agency path |
| Comment | No | Text | Application or permit notes |
| Status | No | Dropdown | Feature Settings permit statuses; bottom of form |
| Status Date | No | Date | With Status |

Issued By contact-management fields (address, phone, etc.) follow the agency contact record; exact extra boxes on “Enter New Agency” are **not enumerated in help**.

### Linked files (step 2)

48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records.

## What Sage CM saves

- **Header record:** Type, subject, application #/date, permit #/date/expire, pulled-by, issued-by agency, comments, status, status date, prime contract.
- **Line / child records:** None documented.
- **System-generated values:** None required beyond defaults (project number).
- **Files / attachments:** Linked files (permit PDFs, drawings).
- **Audit / workflow fields:** Status + Status Date; Expire Date for alerts.

## Statuses and lifecycle

Statuses are **tenant-configured** (Feature Settings). Help does not publish a fixed Open/Closed list.

Typical sequence implied by fields: application (# + date) → issued permit (# + date) → expire date → status/status date updates. Download/print permit is a first-class function.

## Dates that drive alerts

| Feature | Date |
|---|---|
| Permits | Expire date |

Application Date, Permit Date, and Status Date are not on the alerts table.

## Relationships

- **Upstream:** Feature Settings permit types/statuses; project directory (pulled by); Contact Management agencies; prime contract.
- **Downstream:** QC Calendar expire alerts; download permit; linked files.
- **USIS:** `documents.document_type` includes `permit` (file classification only). Daily pretask has free-text `required_permits`.

## Reports and exports

- Download a permit.
- Edit / add functions on overview.
- No Team Open Items row.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Permit application/issued record | none | none |
| Permit file | `documents.document_type = permit` | stub |
| Required permits (PTP) | `daily_pretasks.required_permits` | none (text on pretask) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Permits/PermitsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Permits/PermitsAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/document.py`
  - `backend/app/models/safety.py`
