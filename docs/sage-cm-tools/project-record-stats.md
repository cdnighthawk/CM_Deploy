# Project record stats

Status: complete
Sage CM module: Projects — General Info
Official help: https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm

## Purpose

**Project record stats** is a Project Home **General Info** view that counts records by feature for the selected project (how many RFIs, submittals, POs, etc.). It is a dashboard of **volumes**, not a form you fill out. Official help lists it on the Project menu but does not publish a dedicated “Record stats” field page. Contact Management and Equipment use the same **Stats** pattern (Active counts, three-dot Actions).

## Where it lives

- Project Home → **Project record stats** (General Info)
- Related: Contact Management Insights; Project Insights (Active Projects); Lead Insights (Active Leads); Equipment Stats; Internal Cost Database Stats
- Distinct from **Project analytics** (financial dashboards) and **Reports**
- Mobile / TeamLink: not listed

## Who uses it

- PMs glance at open volume
- Admins jump from a stats count into a list (Contact Management Stats click-through is documented for companies)

## Prerequisites

- A project (or the global module, for Insights stats)
- Security: counts follow the user’s feature permissions (same rule as alerts)

## What the user fills out

No create/edit form. User controls that **are** documented on similar stats/insight pages:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Feature / row | n/a | Display | One row per module feature (menu parallels: RFIs, Submittals, POs, …) |
| Active / total count | n/a | Number | Contact Management Stats uses an **Active** column; project record stats column headers are **not confirmed in help** |
| Actions on a row | n/a | Menu | Insights rows open Add Manually / Import (documented for Companies, Projects, Leads). Whether project record stats rows have Actions is **not confirmed in help** |

Do not invent columns such as “Overdue” or “This week” unless a later help page lists them.

## What Sage CM saves

- Header record: none — computed from existing project records
- Line / child records: none
- System-generated values (IDs, numbers, dates, totals): per-feature counts
- Files / attachments: none
- Audit / workflow fields: none

## Statuses and lifecycle

Live counts. Archived projects may be excluded until reactivated (export help says reactivate archived projects for some reports). Exact inclusion rules for record stats are **not confirmed in help**.

## Dates that drive alerts

None. Stats are not the alerts calendar.

## Relationships

- Upstream: every project feature that creates records
- Downstream: click-through to that feature’s list (confirmed for Contact Management Stats; assume similar UX)

## Reports and exports

Use **Reports** / log reports for exportable counts. Record stats itself has no export page in help.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Per-feature project counts | none | none |
| Project home | `construction/project-detail.html` tabs | stub |
| Calendar aggregates | `_calendar_service.py` (dates, not counts) | none |
| HRMS / safety dashboards | other modules | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_AddManual.htm (Insights/Stats pattern)
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportEquipmentItems.htm (Equipment Stats pattern)
- Local files reviewed
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/project-detail.html`
  - `backend/app/api/_calendar_service.py`
