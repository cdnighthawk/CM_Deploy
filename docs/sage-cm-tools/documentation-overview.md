# Documentation overview

Status: complete
Sage CM module: Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm

## Purpose

The Documentation module is the project (and lead) home for field and office records that prove what happened on site: progress photos, daily logs, meeting minutes, work orders, and owner-furnished items. It is not correspondence (RFIs, submittals, issues) and not QC/Safety. The Documentation Overview page is the hub for the Documentation Calendar, Team Open Items email, and navigation into each documentation tool.

## Where it lives

- **Project Home** (and Lead Home where the feature exists): Documentation section.
- **Documentation Overview**: module hub on the project/lead home; includes Documentation Calendar and Team Open Items (Related Functions).
- **Record lists / forms**: Photos, Daily Logs, Meetings, Work Orders, Owner Items — each is a list plus add/edit form.
- **Home Alerts tab**: daily log date, meeting date, meeting item due dates, work order issue date (owner items are open-item email only, not listed on the alerts calendar).
- **Mobile**: Photos, Daily Logs, Work Orders (R/E/A/D as listed in the iOS matrix). Meetings and Owner Items are not listed as mobile features.
- **TeamLink**: photo albums with Show In Portal; meeting/WO/owner-item follow-up via open-items email hyperlink + security code. Internal employees cannot use TeamLink.

## Who uses it

- Superintendents and PMs create daily logs, photos, meetings, and work orders.
- Field crews update daily logs and photos from the mobile app.
- Coordinators email meeting invitations/minutes and open items to architects, owners, and subcontractors.
- Accounting/PMs convert approved work orders into COs, SCOs, POs, or prime invoices (job cost does not move until that conversion).
- External TeamLink collaborators receive open-item emails; they cannot use the portal as internal employees.

## Prerequisites

- Project (or lead, for Photos and some checklists elsewhere).
- Prime contract selected on most documentation records.
- Companies/contacts in the **project directory** (recorded-by, attendees, issued-to, supplier, reviewer).
- Feature settings: Settings → Feature Settings → Documentation (meeting types, WO types, daily log activity types).
- Cost database / job cost codes when importing labor, equipment, or WO items.
- File library on the same lead/project if linking existing drawings, specs, or photos.

## What the user fills out

The overview itself is not a data-entry form. Users pick a company/contact and send Team Open Items, or open a child tool. Documentation tools and the fields Sage documents for each:

| Tool | User-entered header (confirmed) | Child / line data (confirmed) |
|---|---|---|
| Photos | Album name; Show In Portal | Location; comments/name (searchable); Prevent Photo Deletion; link to feature/record |
| Daily Logs | Daily Log Date; Prime Contract; Recorded By Company/Contact; Notes; Import Previous Day | Visitors; Major Material Deliveries; Major Equipment; Workforce; Weather and Site Conditions; Activities; linked files |
| Meetings | Meeting #; Date; Prime Contract; Meeting Type; Start/Finish Time; Location; Subject; Meeting Purpose; Facilitator; Note Taker; next meeting Date/Start/Finish/Location | Attendees; New/Old Business items (Item #, Subject, Discussion, Category, Responsible Company/Contact, Due Date, Closed, conclusion comments); linked files |
| Work Orders | Issue Date; WO #; Subject; WO Type; Issued By / Issued To; Description; references; Status; Status Date; Billable Status; Address Type; Cost Reviewer | WO items (Item #, Description, Qty, Units, Cost/Sell Rate, Cost Code, Tax, Resource); linked files |
| Owner Items | Supplier Company/Contact; Actual Delivery (confirmed as open-item filters) | Remaining create/edit fields are **not confirmed in help** — dedicated Owner Items add page was not found |

### Documentation Overview / Team Open Items

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes (to filter) | Directory company | From project/lead directory |
| Contact | No | Directory contact | If omitted, Sage shows items assigned to the company only |
| Open item # (review) | No | Hyperlink | User can open an item and drop it from the email list before send |

## What Sage CM saves

- **Header record:** No standalone “overview” entity. Child feature headers live on Photos albums, Daily Logs, Meetings, Work Orders, Owner Items.
- **Line / child records:** See each tool file. Open-item snapshot is computed at email time, not stored as its own document type.
- **System-generated values:** Record numbers (Meeting #, WO #, etc.); daily log date defaults to today; file upload replaces unsupported filename characters with `_`.
- **Files / attachments:** Linked files on Daily Logs, Meetings, Work Orders (and other listed features). Upload: up to 48 files per add wizard step, 500 MB total; no `.EXE`; same-project/lead only when linking existing. Photos are a first-class library plus albums.
- **Audit / workflow fields:** Open-items email includes a portal hyperlink and security code. WO costs stay off project analytics until imported into CO / SCO / prime invoice / PO.

### Documentation open-item rules (email)

| Feature | Filter criteria |
|---|---|
| Meeting items | Mtg Item Status = Open; Company Responsible = selected company/contact |
| Owner items | Actual Delivery is null; Supplier = selected company/contact |
| Work order issued to | WO Status = Open; Issued To = selected company/contact |
| Work order reviewer | WO Status = Open; Reviewer = selected company/contact; Review Comments is null |

## Statuses and lifecycle

- Overview has no status.
- Daily logs: created, then sections filled; listed by date.
- Meeting items: Open until Closed checkbox + conclusion comments.
- Work orders: Open (email/alerts) → Approved (Status Date set when Approved) → Close a WO.
- Owner items: treated as open while Actual Delivery is null.
- Photos: no workflow status; Prevent Deletion locks delete.

## Dates that drive alerts

From the official alerts calendar (Documentation):

| Feature | Date |
|---|---|
| Daily log | Daily log date |
| Meetings | Meeting date |
| Meetings new business item | Item due date |
| Meetings old business item | Item due date |
| Work orders | Issue date |

Owner items are **not** listed on the alerts calendar. They appear on Team Open Items when Actual Delivery is null.

Documentation Calendar is on Project Home → Documentation Overview.

## Relationships

- **Upstream:** Project, prime contract, project directory, drawings/specs, cost database, labor/equipment timecards, POs, estimates.
- **Downstream:** Daily log quantities can feed WO PO import and (Unit Price) prime invoices; WOs convert to CPR/CO, prime invoice, PO, subcontract, or SCO; meeting items roll into the next meeting; photo albums share via TeamLink; open-items email uses TeamLink method 1 (hyperlink + code).
- **Sibling modules:** Correspondence (issues/RFIs/submittals), QC and Safety, Scheduling (import scheduling activities onto daily logs).

## Reports and exports

- Per-tool detail/log reports (daily log, meeting minutes HTML email, WO print/share).
- Documentation Calendar and Home Alerts list/calendar.
- Team Open Items email from Documentation Overview or Project Team → Team Open Items.
- Photos: Actions → Download All Photos (ZIP link emailed to the user).

## USIS / CM_Deploy mapping

USIS has field daily reports and jobsite photos, not a Sage Documentation Overview hub, meetings module, WO workflow, or owner-furnished items tracker.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Documentation Overview / Calendar | none | none |
| Team Open Items email | none | none |
| Daily log | `daily_reports` / `GET/PUT /api/v1/projects/:id/daily-reports` / field app | partial |
| Photos / albums | `field_photos`, `documents` (`document_type=photo`) | partial |
| Meetings / minutes | W3CRM `construction/mom.html` (generic MOM, not Sage meetings) | none |
| Work orders | `corecon_transactions.work_order_*` (import columns only) | stub |
| Owner items | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/UploadingFilesFromFeature.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
  - Child tool pages listed in `photos.md`, `daily-logs.md`, `meetings.md`, `work-orders.md`, `owner-items.md`
- Local files reviewed
  - `backend/app/models/field_ops.py`
  - `backend/app/models/document.py`
  - `backend/app/models/corecon_transaction.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/mom.html`
