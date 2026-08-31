# Comply notices

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/ComplyNotice/ComplyNoticeAddManually.htm

## Purpose

A comply notice is a formal QC letter from one directory company to another (usually GC → contractor) requiring corrective action. The response due date lands on the Quality Control Calendar and Home Alerts. The notice stays on Team Open Items while Status is Open and Response Date is null.

## Where it lives

- **Project Home** → Quality Control / QC and Safety → **Comply Notices**.
- Add wizard: general information → linked files.
- **Quality Control Overview** → Team Open Items; Quality Control Calendar.
- **Mobile:** Comply notices R, E, A, D; **Email option: Yes**.

## Who uses it

- From company: almost always your firm (issuer).
- To company: contractor responsible for compliance (project directory).
- Optional From/To contacts for addressing and email.
- Recipient follows up until Response Date is entered.

## Prerequisites

- Project; From and To companies in the **project directory**.
- Optional Type (Feature Settings — exact type list **not enumerated in help**).
- Optional references to prime contract, CPR/CO, subcontract, SCO, drawing, location, spec section.

## What the user fills out

### Header (Actions → Add Manually, step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | |
| Issue Date | No | Date | Defaults to today |
| Comply Notice # | No | Text/number | Auto-generated; user may modify |
| Type | No | Dropdown | “Optionally select” |
| Subject | Yes | Text | |
| From Company | Yes | Directory company | Usually your firm |
| From Contact | No | Directory contact | |
| To Company | Yes | Directory company | Contractor responsible for compliance |
| To Contact | No | Directory contact | Open-item match uses Issued To company/contact |
| Address Type (both companies) | Yes (help: specify) | Address type | For both From and To |
| Description | No | Text | |
| Response Due Date | No | Date | QC Calendar + Home Alerts |
| Prime Contract # | No | Reference | |
| CPR / CO # | No | Reference | |
| Subcontract # | No | Reference | |
| SCO # | No | Reference | |
| Drawing | No | Reference | |
| Location | No | Text | |
| Spec. Section | No | Text | |
| Other | No | Text | |

**Status** and **Response Date** / **Date responded** are used by open items and alerts. The add-wizard page does not list Status as a step-1 control; treat Status and Response Date as persisted workflow fields confirmed on OpenItemsEmail and AlertsCalendar (edit-form labels beyond those names are **not confirmed in help**).

### Linked files (step 2)

48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records; same project/lead only.

## What Sage CM saves

- **Header record:** Number, issue date, type, subject, From/To company+contact, address types, description, references, due date, status, response date.
- **Line / child records:** None documented (notice is a single record + files).
- **System-generated values:** Comply Notice #; Issue Date default today.
- **Files / attachments:** Linked images/PDFs.
- **Audit / workflow fields:** Status Open; Response Date null → Team Open Items for Issued To; Response due date and Date responded on alerts.

## Statuses and lifecycle

| Status / date | Effect |
|---|---|
| Open + Response Date null | Team Open Items for Issued To company/contact |
| Response Date set | Drops off open items |
| Response Due Date | QC Calendar + Alerts |
| Date responded | Alerts table (Quality control) |

Exact Status pick-list values other than **Open** are **not confirmed in help**.

## Dates that drive alerts

| Feature | Date |
|---|---|
| Comply notice | Response due date |
| Comply notice | Date responded |

Issue Date is not on the alerts table.

## Relationships

- **Upstream:** Project directory; optional contract/drawing/spec references; photos.
- **Downstream:** QC Calendar; Team Open Items; mobile email.
- **Sibling:** Punchlist (defect tracking) and SHA (hazards) are different tools.

## Reports and exports

- Record detail / print (standard feature pattern; specific template name **not confirmed in help**).
- Mobile email.
- Team Open Items email.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Comply notice | none | none |
| Correspondence issues | `tracker_issues` / `construction/issues.html` | none (not a comply notice) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/ComplyNotice/ComplyNoticeAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `backend/app/models/issue.py`
