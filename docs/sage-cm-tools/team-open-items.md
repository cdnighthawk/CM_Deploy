# Team open items

Status: complete
Sage CM module: Project Team / module overviews
Official help: https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm

## Purpose

Team Open Items is a **follow-up inbox per company/contact**: expired insurance/licenses plus unfinished project work assigned to that firm. You review the list and email the external member a TeamLink link and security code. It is not a task you create; it is a **query** over other records.

## Where it lives

- Lead or Project Home → **Team Open Items** (Project Team)
- Also: Procurement, Correspondence, Documentation, Quality Control, and Safety **overview** pages → Team Open Items (Related Functions)
- Open items also appear **at the top of Project Home** (October 2023)
- TeamLink: email hyperlink + security code
- Mobile: not listed as its own add module

## Who uses it

- PMs chase architects and subcontractors
- Compliance staff chase expired COIs/licenses
- External contacts work the list in TeamLink

## Prerequisites

- Project or lead exists
- Company/contact is referenced on the source records
- Email address on the contact for Send Email

## What the user fills out

### Send email

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes | Lookup | |
| Contact | No | Lookup | If omitted, list is **all items assigned to the company** |
| Open items list | n/a | Review | Click item # to open the source record; remove by fixing the source, not by deleting from this list |
| Send Email | Yes to notify | Action | Includes portal hyperlink and security code |

No other create fields. Inclusion rules are **filters on other features**:

### Company profile

| Feature | Open when |
|---|---|
| Insurance | Expired general or project-specific policies for the company |
| Licenses | Expired licenses for the company |

### Contract administration

| Feature | Open when |
|---|---|
| CPR (impacted company) | Status Pending or Pending Submission; Impacted Company = selected; Impacted company Response Due Date is **null** |

### Procurement

| Feature | Open when |
|---|---|
| Procurement RFP | Vendor Locking = False; bidder = selected; Date Responded is **null** |

### Correspondence

| Feature | Open when |
|---|---|
| Issues | Status Open; Company Involved = selected; Response Date null |
| Journal | Status Open; Respondent = selected; Response Date null |
| RFI | Status Open; Respondent = selected; Response Date null |
| Submittal originator | Status Open; Originator = selected; Date Item Rec'd From Originator null |
| Submittal respondent | Status Open; Respondent = selected; Response Date null |

### Documentation

| Feature | Open when |
|---|---|
| Meeting items | Item Status Open; Company Responsible = selected |
| Owner items | Actual Delivery null; Supplier = selected |
| Work order issued to | WO Status Open; Issued To = selected |
| Work order reviewer | WO Status Open; Reviewer = selected; Review Comments null |

### Quality control

| Feature | Open when |
|---|---|
| Comply notice | Status Open; Issued To = selected; Response Date null |
| Punchlist item | Status Open; Responsible = selected; Completion Date null |
| Test and inspection | Overall Status Open; Sample Test Status Pending; Testing Company = selected |

### Scheduling

| Feature | Open when |
|---|---|
| Scheduling task | Status not Completed; assigned resource = selected |

## What Sage CM saves

- Header record: none — computed list
- Line / child records: none
- System-generated values (IDs, numbers, dates, totals): email security code
- Files / attachments: none on the open-items row
- Audit / workflow fields: sending the email does not close items; closing happens on the source record

## Statuses and lifecycle

Items disappear when the source record no longer matches the filter (responded, completed, expired insurance replaced, etc.).

## Dates that drive alerts

Open Items uses **null completion/response dates** and **expired** compliance dates. Those same source dates also appear on the alerts calendar (see `alerts.md`).

## Relationships

- Upstream: all features in the tables above
- Downstream: TeamLink follow-up email

## Reports and exports

Email only. No open-items export page in help.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Cross-feature open-item query + email | none | none |
| RFI / submittal / issue open | `rfi`, `submittal`, `issue` statuses | partial |
| In-app notify | `hrms_notifications` / `_in_app_notifications.py` | stub |
| Calendar due dates | `_calendar_service.py` | partial |
| Expired company insurance/licenses | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
- Local files reviewed
  - `backend/app/models/rfi.py`
  - `backend/app/models/submittal.py`
  - `backend/app/models/issue.py`
  - `backend/app/api/_in_app_notifications.py`
