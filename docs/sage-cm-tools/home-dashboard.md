# Home dashboard

Status: complete
Sage CM module: Platform (Home)
Official help: https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm

## Purpose

The Sage Construction Management **Home** page is the tenant-wide landing surface: **Alerts** (list or calendar), user alert subscriptions, and (on mobile) My Records plus Clock In/Out. It is not Project Home. Project Home is a separate per-job menu (open items, record stats, libraries, modules).

## Where it lives

- Browser: **Home** after login → **Alerts** tab → Set Alerts; Alerts icon → List or Calendar
- Mobile Home: **My Records** (timecards, expenses, daily logs); **Clock In / Out** with geotagging; workflow approvals if enabled
- Distinct URLs/pages: Lead Home, Project Home, module overviews, Analytics BI dashboards
- TeamLink has Owner / Vendor dashboards (referenced records), not this Home

## Who uses it

- Every licensed user sees alerts allowed by security
- Users choose which features they subscribe to
- Field staff use mobile Home for time and “my records”

## Prerequisites

- User account and security role
- Closed/archived leads and projects **do not** appear in calendars or the alerts list
- Checklist item alerts roll up to **one** notification (Date = earliest item due; Subject = checklist name)

## What the user fills out

Home is not a business-record form. User-editable settings:

### Set Alerts

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Feature checkboxes | No | Multi-select | Each feature in the alerts table (leads, projects, RFP, insurance, licenses, to-dos, RFIs, …) |
| Assigned vs not-assigned schedule tasks / to-dos | No | Choice | Feb 2026: assigned to you, not assigned to you, or both |

### View

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Alerts List vs Alerts Calendar | Yes when opening the icon | Choice | |
| Feature filters (on Lead/Project Home Alerts) | No | Checkboxes | Clear features to hide |

There is no “widget layout” editor on Home in official help. Custom KPI boards are **Analytics / BI dashboards** (separate README item).

### Mobile Home (overview)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Clock In / Out | n/a | Action | Optional clock out crew / entire crew |
| My Records shortcuts | n/a | Nav | Timecards, expenses, daily logs |

## What Sage CM saves

- Header record: per-user alert subscription preferences
- Line / child records: none
- System-generated values (IDs, numbers, dates, totals): alert rows derived from other modules’ dates
- Files / attachments: none
- Audit / workflow fields: security role filters what appears

## Statuses and lifecycle

Alerts appear while the source is open and the lead/project is not closed. Completing a to-do or updating AccountingLink payment can **remove** invoice/bill payment-due alerts.

## Dates that drive alerts

See `alerts.md` for the full official table. Home is the aggregator.

## Relationships

- Upstream: every feature that writes a due/expire date
- Downstream: click-through to the source record; mobile time entry

## Reports and exports

None on Home. Use Reports and Project analytics.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Home landing | `usis-dashboard.html`, `usis-dashboard-dark.html` | stub |
| Header bell | `hrms_notifications` / `_in_app_notifications.py` | partial |
| Project calendar | `_calendar_service.py` (procurement, schedule, RFI, submittal, RFP, milestones) | partial |
| Per-user alert feature subscriptions | none | none |
| Mobile clock in/out | `_time_clock_service.py` | partial |
| Sage-style Home alerts tab | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileAppOverview.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/February-2026/February-2026-WhatsNew.htm
- Local files reviewed
  - `backend/app/api/_in_app_notifications.py`
  - `backend/app/api/_calendar_service.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/elements/deznav-construction.html`
