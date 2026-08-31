# Alerts

Status: complete
Sage CM module: Alerts and calendars
Official help: https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm

## Purpose

Alerts surface **due, response, delivery, expiration, and reminder dates** from across Sage Construction Management in one list or calendar. What you see depends on security, your Set Alerts subscriptions, and whether the lead/project is still open.

## Where it lives

- Home → **Alerts** tab → Set Alerts
- Alerts icon → Alerts List or Alerts Calendar (all active leads/projects)
- Lead or Project Home → **Alerts** (General Info) with feature filters
- Feature calendars: Contract Admin, Procurement, Correspondence, Documentation, QC, Safety, Scheduling (General and Project To Dos)
- Mobile: Alerts **read**; Workflow alerts and approvals **read/edit**
- TeamLink: not this calendar; vendors use portal records

## Who uses it

- Every user for their assigned dates
- Bid/PM/Sales contacts for bid due
- Compliance for insurance/license expiration
- Accounting for payment due (until AccountingLink marks paid)

## Prerequisites

- User security role
- Set Alerts feature selection
- Lead/project not closed/archived
- To-dos: open, and assigned to or authored by the user (unless Feb 2026 “not assigned” option is on)

## What the user fills out

Alerts are **not created as standalone records**. Users only configure subscriptions and filters:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Feature subscription | No | Checkboxes | Home → Set Alerts |
| List vs Calendar | No | Choice | |
| Feature filters on project/lead Alerts | No | Checkboxes | |
| Assigned / not assigned tasks | No | Choice | Feb 2026 |

Source records own the dates. Official alert drivers:

### Bids

| Feature | Date |
|---|---|
| Leads | Owner bid due date; user is Bid, PM, or Sales Contact |
| Projects | Owner bid due date; user is Bid, PM, or Sales Contact |
| Estimate RFP packages | Bid due date |

### Contact Management

| Feature | Date |
|---|---|
| Company insurance | Expiration date (within 60 days) |
| Company license | Expiration date (within 60 days) |

### Contract administration

| Feature | Date |
|---|---|
| Allowance package | Required completion date; Follow up date; Actual completion date |
| CPR | Impacted company response due date |
| Prime contract invoices | Payment due date * |

\* Removed when AccountingLink Update Payment is applied.

### Procurement

| Feature | Date |
|---|---|
| Procurement RFP packages | Bid due date |
| PO items | Est. delivery date |
| Bills | Payment due date * |
| Subcontract invoices | Payment due date * |

### Correspondence

| Feature | Date |
|---|---|
| Issues | Due date |
| Journals | Reminder date |
| Journal respondents | Response due date; Date responded |
| RFI respondents | Response due date; Date responded |
| Submittal items originator | Due from originator; Received from originator; Status response sent back to originator |
| Submittal items material required on site and design review | Review planned submission; Review completion; Return to originator; Material required on site |
| Submittal items material delivery | Anticipated / estimated / actual delivery |
| Submittal respondents | Respondent due date; Date responded |
| Transmittals | Due date |

### Documentation

| Feature | Date |
|---|---|
| Daily log | Daily log date |
| Meetings | Meeting date |
| Meeting new/old business item | Item due date |
| Work orders | Issue date |

### Scheduling

| Feature | Date |
|---|---|
| General to-do * | Due date |
| Project to-do * | Due date |
| Scheduling task assigned | Task start date |
| Scheduling task not assigned | Task start date |

### Quality control

| Feature | Date |
|---|---|
| Checklist inspection | Review date |
| Checklist item | Due date (rolled up on Home as one alert named after the checklist) |
| Comply notice | Response due date; Date responded |
| Permits | Expire date |
| Punchlist inspection | Inspection date |
| Punchlist item | Due date |

### Safety

| Feature | Date |
|---|---|
| Safety meeting discussion item | Due date |

## What Sage CM saves

- Header record: per-user alert preferences
- Line / child records: none (derived)
- System-generated values (IDs, numbers, dates, totals): checklist rollup Date and Subject
- Files / attachments: none
- Audit / workflow fields: security; AccountingLink payment clears some payment alerts

## Statuses and lifecycle

Visible while source dates apply and the parent lead/project is open. Completing/responding/paying removes or updates the row.

## Dates that drive alerts

The tables above **are** the date list. Do not add drawing release dates or estimate review due unless help later lists them.

## Relationships

- Upstream: every dated feature
- Downstream: Home list/calendar; feature calendars; mobile alerts
- Related but separate: **workflow alerts and approvals** (mobile read/edit; own README file)

## Reports and exports

Calendar views only. No alerts export page in help.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Cross-module alert subscriptions | none | none |
| In-app bell | `hrms_notifications` | partial |
| Project calendar events | `_calendar_service.py` (`procurement_order`, `procurement_delivery`, `schedule`, `rfi`, `submittal`, `rfp`, `project_milestone`) | partial |
| RFI/submittal/RFP due dates | those models | partial |
| Insurance/license 60-day alerts | none | none |
| To-do / checklist / CPR / invoice payment alerts | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/February-2026/February-2026-WhatsNew.htm
- Local files reviewed
  - `backend/app/api/_calendar_service.py`
  - `backend/app/api/_in_app_notifications.py`
  - `backend/app/models/hrms_core.py`
