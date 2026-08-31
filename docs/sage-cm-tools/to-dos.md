# To-dos

Status: complete
Sage CM module: Scheduling
Official help: https://help.sagecm.intacct.com/Content/Modules/Import/ImportProjectToDos.htm

## Purpose

To-dos are lightweight tasks: **general** (not job-specific) and **project** to-dos. They have author, assignee, due date, priority, category, status, status date, and percent complete. They appear on the alerts calendar when open and assigned to or authored by the user. They are not full Gantt schedule tasks (those are Scheduling tasks).

## Where it lives

- Project Home → **Schedules** → **General and Project To Dos**
- Scheduling Overview → Active Projects Calendar — General and Project To Dos
- Home Alerts (due date)
- Mobile: general and project to-dos **read, edit, add, delete**
- TeamLink: not listed as a vendor to-do tool

A dedicated “Add to-do” HTML page was not fetched; the **Excel import column list** is the official field inventory and matches typical add-form fields.

## Who uses it

- PMs and coordinators assign follow-ups
- Authors track items they created even if unassigned
- Admins define To Do Category in Feature Settings → Scheduling

## Prerequisites

- Project to-dos: project exists; **ProjectNumber** must match
- **TaskAuthorContact** must match a user’s **display name**
- **TaskAssignedToContact** if used must match a user’s display name
- **TaskCategory** must match Settings → Feature Settings → Scheduling → To Do Category

## What the user fills out

### Project to-do (import = form fields)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project Number | Yes | Text | Import `ProjectNumber` |
| Task Description | Yes | Text | Import `TaskDescription` |
| Task Due Date | No | Date | DD-MMM-YYYY, MM-DD-YYYY, or YYYY-MM-DD |
| Task Author Contact | Yes | Text | User display name |
| Task Assigned To Contact | No | Text | User display name |
| Task Priority | No | Lookup | **High**, **Medium**, **Low** |
| Task Category | No | Lookup | Must match To Do Category setting |
| Task Status | No | Lookup | **Not Started**, **On Hold**, **Started**, **Waiting on Customer**, **Waiting on Vendor**, **Completed** |
| Task Status Date | No | Date | |
| Task Percent Complete | No | Integer | e.g. 50 for 50% |

### General to-do

Same task fields **without** Project Number (implied by “General and Project To Dos”). Extra general-only fields: **not confirmed in help**.

## What Sage CM saves

- Header record: to-do with description, due, author, assignee, priority, category, status, status date, percent complete, optional project
- Line / child records: none
- System-generated values (IDs, numbers, dates, totals): none listed
- Files / attachments: not confirmed in help
- Audit / workflow fields: author vs assignee (both see alerts)

## Statuses and lifecycle

Not Started → On Hold / Started / Waiting on Customer / Waiting on Vendor → **Completed**. Alerts require the to-do to be **open (not completed)** and assigned to **or** authored by the user. Feb 2026: alert settings can include tasks assigned to you, not assigned to you, or both; calendar filter for which to-dos appear.

## Dates that drive alerts

- **Due date** — General to-do and Project to-do (Home alerts / calendar)

## Relationships

- Upstream: project (for project to-dos); user display names; To Do Category settings
- Downstream: alerts calendar; distinct from Scheduling **tasks** (task start date alerts)

## Reports and exports

- Excel import of project to-dos (`*.xls`, Sheet1)
- Scheduling calendar views

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| To-do record | none | none |
| W3CRM todo UI | `construction/todo.html`, `todo-detail.html` — template list (Pending/Completed), not wired to Sage fields | stub |
| Schedule items | `project_schedule_items` — dates/tasks, not to-do status enum | none |
| Calendar | `_calendar_service.py` categories do not include to-do | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportProjectToDos.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/February-2026/February-2026-WhatsNew.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/todo.html`
  - `backend/app/models/project_schedule.py`
