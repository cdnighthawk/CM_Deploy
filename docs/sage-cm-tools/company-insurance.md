# Company insurance

Status: complete
Sage CM module: Contact Management
Official help: https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Insurance.htm

## Purpose

Insurance records live on a company’s **Compliance** tab so subcontractors and suppliers can prove coverage. Sage alerts users when a policy is within 60 days of expiration, can email an expiration notice, and lists expired policies as Team Open Items for that company.

## Where it lives

- Global nav: **Contact Management** → Companies → Company Profile → **Compliance** tab → Insurance section
- Not a lead/project menu item; optional **Project #** on the policy scopes it to one job
- Mobile: company records are read-only; insurance edit is not listed as a mobile add/edit feature
- TeamLink: expiration notices can Grant Access on linked files so the vendor can open them in the portal

## Who uses it

- Compliance / AP staff add and update policies
- PMs check coverage before awarding POs or subcontracts
- Administrators email expired-insurance notices
- External vendors receive notices and may upload files through TeamLink when granted access

## Prerequisites

- Parent company must exist
- Insurance types must exist (resource center: Company insurance types; exact settings path not confirmed in help beyond Contact Management settings)
- **Insurance Type**, **Insurance Company**, **Amount**, and **Expire Date** are the fields the add procedure requires the user to enter/select

## What the user fills out

### Insurance section (Add)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Insurance Type | Yes | Lookup | Selected first on Add |
| Insurance Company | Yes | Text | Carrier name |
| Insurance Contact | No | Text | |
| Phone # | No | Text | Carrier/contact phone |
| Policy # | No | Text | |
| Amount | Yes | Currency | Coverage amount |
| Project # | No | Lookup | Blank = applies to **all active projects** |
| Expire Date | Yes | Date | Drives 60-day alerts and expiration email |
| Linked File | No | File | Choose File from local drive (certificate of insurance) |

Help also lists **Import company insurance information from a Microsoft Excel file** on the Contact Management resource center. The import column list was not on the add page; treat extra import columns as not confirmed in help.

### Expiration notice email (Actions)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Template | Yes | Lookup | Actions → Send Insurance Expiration Notice |
| Recipients List | Yes | Contacts | |
| CC List | No | Contacts | Import recipients |
| Subject / Body | No | Text | Editable |
| Grant Access (per linked file) | No | Checkbox | Shares file in TeamLink; files here are **not** email attachments |
| Email Upload Attachments | No | Files | Attached to the email only; not added to Linked Files |

## What Sage CM saves

- Header record: company-scoped insurance row (type, carrier, contact, phone, policy #, amount, optional project, expire date)
- Line / child records: none; one row per policy
- System-generated values (IDs, numbers, dates, totals): internal insurance record ID; general vs project-specific distinction when Project # is blank
- Files / attachments: optional Linked File on the policy
- Audit / workflow fields: not confirmed in help (no draft/approved status on the insurance row)

## Statuses and lifecycle

No draft/pending/approved status in help. Lifecycle is **current → expiring (within 60 days) → expired**. Expired general and project-specific policies appear in Team Open Items for the selected company. You cannot delete the parent company while insurance records remain.

## Dates that drive alerts

- **Expire Date** — Contact Management alert within 60 days
- Team Open Items filter: insurance records that **have expired** for the selected company (general and project-specific)

## Relationships

- Upstream: company; optional project
- Downstream: alerts calendar, expiration email, Team Open Items, compliance checks before procurement (process, not a hard lock confirmed in help)

## Reports and exports

- Email expiration notice from company Actions
- Resource center lists Excel import of insurance
- Standard/custom log reports for Contact Management (resource center)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Company insurance policy | none | none |
| Insurance expire alerts | none (USIS alerts are HRMS in-app + project calendar dates) | none |
| Certificate file | none on company; `documents` is project-scoped | none |
| Safety company docs | `GET/POST /api/v1/safety/company-docs` — OSHA/safety packet, not COI | none |
| W3CRM compliance UI | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Insurance.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Overview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_EmailExpiredInsuranceLicenses.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/ResourceCenter_ContactManagement.htm
- Local files reviewed
  - `backend/app/models/company.py`
  - `backend/app/api/_safety_docs_routes.py`
  - `backend/app/api/_in_app_notifications.py`
