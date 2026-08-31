# Company licenses

Status: complete
Sage CM module: Contact Management
Official help: https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Licenses.htm

## Purpose

Contractor and business licenses are stored on the same company **Compliance** tab as insurance. Sage alerts when a license is within 60 days of expiration, can email a license expiration notice, and lists expired licenses as Team Open Items.

## Where it lives

- Global nav: **Contact Management** → Companies → Company Profile → **Compliance** tab → Licenses section
- Not a project-menu tool; unlike insurance, the add form has **no Project #** field in official help
- Mobile: company records are read-only
- TeamLink: expiration emails can Grant Access on the linked license file

## Who uses it

- Compliance staff enter license type, jurisdiction, and number
- PMs and estimators verify a sub is licensed before ITB/award
- Administrators send license expiration notices

## Prerequisites

- Parent company must exist
- Add form requires **License Type**, **License Location**, and **License #**

## What the user fills out

### Licenses section (Add)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| License Type | Yes | Text / lookup | Help says “Enter” — allowed values not enumerated in help |
| License Location | Yes | Text | Jurisdiction (state, city, or board) |
| License # | Yes | Text | |
| License Date | No | Date | Issue / effective date |
| Expire Date | No | Date | When set, drives 60-day alerts |
| Linked File | No | File | Choose File (scan of license) |

### Expiration notice email (Actions)

Same pattern as insurance: Actions → **Send License Expiration Notice**, then Template, Recipients, CC, Subject, Body, Grant Access on linked files, optional Email Upload Attachments.

## What Sage CM saves

- Header record: company-scoped license row (type, location, number, optional license date and expire date)
- Line / child records: none
- System-generated values (IDs, numbers, dates, totals): internal license ID
- Files / attachments: optional Linked File
- Audit / workflow fields: not confirmed in help; no status field on the add page

## Statuses and lifecycle

No approval workflow in help. Lifecycle is **current → expiring (within 60 days of Expire Date) → expired**. Expired licenses appear in Team Open Items. Company delete is blocked while license records remain.

## Dates that drive alerts

- **Expire Date** — Contact Management alert within 60 days (when the date is populated)
- Team Open Items: licenses that **have expired** for the selected company
- **License Date** is stored but is not listed as an alert driver

## Relationships

- Upstream: company
- Downstream: alerts, expiration email, Team Open Items
- Distinct from employee licenses on the Time & Expenses employee form

## Reports and exports

- Email license expiration notice
- Contact Management log / detail reports (resource center)
- Excel import of licenses is **not** listed on the resource center (insurance import is); do not assume a license import exists

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Company license | none | none |
| License expire alerts | none | none |
| Employee/HR licenses | HR hire wizard `certifications_licenses`; Safety certs on HR dashboard | none |
| W3CRM license UI | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Licenses.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_EmailExpiredInsuranceLicenses.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local files reviewed
  - `backend/app/models/company.py`
  - `backend/app/models/hr.py` (employee-side only)
