# Workflow alerts and approvals

Status: complete
Sage CM module: Home / Workflow / Alerts
Official help: https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_Overview.htm

## Purpose

This is the **inbox**: Home → Workflow tab (and email) for Contract Admin & Procurement approvals, plus Time & Expense approval of subordinates’ cards/expenses, plus the separate **Alerts** list/calendar for due dates across modules. Alerts are not the same as workflow — alerts are date-driven reminders; workflow is value-rule (or manager) approval that locks the transaction.

## Where it lives

- Home → Workflow tab (users who have CA/P feature access).
- Home → Alerts tab → Set Alerts; Alerts icon → list or calendar (all active leads/projects).
- Lead/Project Home → Alerts (General Info) and feature calendars (Correspondence, Procurement, Contract Admin, etc.).
- Email: workflow emails to approvers; alert emails per Set Alerts.
- TeamLink: not the CA/P approver inbox. TeamLink is correspondence response.
- Mobile: alerts/approvals per mobile app; official Apple overview is a companion entry point.

## Who uses it

Approvers named on a rule (or PM alias / admins). Financial Admin / Admin / managers (T&E). Every user with Alerts configured. Field User has limited calendar features (photos/daily logs) and no CA/P workflow tab unless given feature access.

## Prerequisites

- CA/P workflow enabled and at least one matching rule; or T&E workflow + manager/Time Approval Access.
- User Set Alerts feature checkboxes.
- Browser/email for notifications.

## What the user fills out

### Set Alerts (Home → Alerts)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Feature checkboxes | No | Multi | Which due-date families to receive |
| Save | Yes | Action | |

### View alerts

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Alerts List vs Alerts Calendar | Yes | Choice | Global icon |
| Per-project feature filters | No | Checkboxes | Expand Filters on project Alerts |

Checklist item alerts collapse to one row: Date = earliest item due; Subject = checklist name.

### Workflow tab (approve CA/P)

Exact approve-form field labels (comments, approve/reject buttons) were not listed on the overview page. Confirmed behaviors:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Select matching rule | Conditional | Choice | If multiple rules apply to the transaction |
| Approve / Not Approved | Yes | Action | Sage writes transaction status; listing turns green or red |
| Abandon workflow | Conditional | Action | Per AbandonWorkflow setting; then edit and reinitiate |
| Email notification | System | | Sent when the transaction is submitted into workflow |

Before initiate, status can only be Pending. After initiate, header status is disabled.

### T&E approval

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Approve labor / misc expense | Yes | Action | Admin/FA always; managers only with workflow + Timecard Approval on role |
| Employee cannot self-approve | System | | Official table |

### Correspondence response (not Home Workflow, but TeamLink “approval-like”)

Respondents fill Response on RFI/Submittal Respondent Details or portal; coordinator marks Closed. Sequential/Parallel auto-notify is on the record, not this inbox.

## What Sage CM saves

- Header record: none for the inbox. Alerts are computed from source dates. Workflow instances live on the transaction (locked, status, color).
- Line / child records: per-user Set Alerts preferences; Time Approval Access list.
- System-generated values: yellow/green/red listing colors; email send; checklist rollup subject/date.
- Files / attachments: none on the inbox.
- Audit / workflow fields: who approved/abandoned; transaction Status Date still on the source document when Sage updates status.

## Statuses and lifecycle

Alert: appears while the date is relevant and (for to-dos) the item is open. Workflow: Pending (yellow) → Approved (green) or Not Approved (red); abandon returns to editable Pending. Prime invoice / bill / subinvoice payment-due alerts **clear** when AccountingLink Update Payment writes payment info.

## Dates that drive alerts

Official table (abbreviated; full page has every row):

- Leads/Projects: owner bid due (if user is bid/PM/sales contact)
- Company insurance/license: expiration within 60 days
- Allowance: required/follow-up/actual completion
- CPR: vendor response due
- Prime/bill/subinvoice: payment due
- Procurement RFP: bid due; PO item est. delivery
- Correspondence: see correspondence-overview.md
- Documentation: daily log date, meeting date, meeting item due, WO issue date
- Scheduling: to-do due; task start
- QC: checklist review/item due, comply due/responded, permit expire, punch inspection/item due
- Safety: safety meeting discussion item due

Labor/equipment timecards and misc expenses are **not** on this alerts table (they use T&E workflow/email instead).

## Relationships

- Upstream: workflow rules; Set Alerts; source records’ dates.
- Downstream: locked financials; AccountingLink payment clears some AP/AR alerts.

## Reports and exports

Alerts calendar view; no “alerts log report” name confirmed. Workflow is on-screen + email.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Home workflow inbox | `workflow_instances` / steps `assignee_user_id` | partial |
| Date alerts calendar | `usis-calendar.html` | stub |
| HRMS notifications | `hrms_notifications` | partial |
| RFI notification log | `rfi_notification_log` | implemented |
| T&E manager approve | timesheet/expense `status` + `approver_user_id` | partial |
| Alerts “Set Alerts” prefs | none | none |

## Sources

- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_Overview.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_TimeExpenses_Overview.htm
- https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local: `backend/app/models/workflow.py`, `backend/app/models/hrms_core.py` (`HrmsNotification`)
