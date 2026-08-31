# Scheduling overview

Status: complete
Sage CM module: Scheduling
Official help: https://help.sagecm.intacct.com/Content/Modules/Scheduling/ResourceCenter_Scheduling.htm

## Purpose

Scheduling Overview is the project hub for Gantt schedules, tasks, resource/calendar/comments/properties views, look-aheads, and the **Active Projects Calendar** for general and project to-dos. A project can hold **multiple schedules** (e.g. design vs construction, or one per structure). Task start dates drive Home Alerts; incomplete assigned tasks appear on Team Open Items.

## Where it lives

- **Project Home** → Scheduling section → **Schedules** (Gantt list) and **Scheduling Overview**.
- Overview → **Active Projects Calendar - General and Project To Dos**.
- Home Alerts / Alerts icon: to-do due dates; scheduling task start dates (assigned and not assigned).
- **TeamLink:** shared online Gantt — Owner and Architect roles read-only; Vendor (subcontractor) sees **only assigned tasks**.
- **Mobile:** Schedules and tasks **R, E** (no Add/Delete in the iOS matrix). To-dos R, E, A, D.

## Who uses it

- PMs/schedulers create schedules, indent WBS, set predecessors, baselines, and calendars.
- Superintendents update % complete and look-aheads.
- Assigned **company + contact** (email notifications) and **equipment** resources.
- External TeamLink owner/architect (read-only chart); subs (assigned tasks only).
- Admins: Settings → Feature Settings → Scheduling (work calendars, default numbering).

## Prerequisites

- Project; optional prime contract (recommended when multiple lots/contracts).
- Work **Calendar** defined in Feature Settings → Scheduling (work days and holidays).
- Directory companies/contacts for assignments (contact required because Sage emails task notifications).
- Optional equipment records for equipment assignments.
- Excel or Microsoft Project XML if importing instead of manual entry.

## What the user fills out

The overview itself is navigation + calendars, not a create form. Users configure:

| Surface | User input |
|---|---|
| Scheduling Overview / Active Projects Calendar | View to-dos across active projects |
| Set Alerts (Home) | Feature checkboxes including scheduling tasks and to-dos |
| Team Open Items | Company/contact — incomplete tasks assigned to that resource |
| Collaborate on live schedule | TeamLink roles: Vendor, Architect, Owner |

Schedule **header** and **task** fields are documented in `schedules-and-tasks.md`.

### Overview-related open items and alerts

| Feature | Filter / date |
|---|---|
| Scheduling task (email) | Task Status **not** Completed; assigned resource = selected company/contact |
| General to-do * | Due date |
| Project to-do * | Due date |
| Scheduling task assigned | Task start date |
| Scheduling task not assigned | Task start date |

\* To-dos must be open, not completed, and assigned to the user or authored by the user.

## What Sage CM saves

- **Header record:** Schedule (number, title, calendar, prime contract, comments) — see schedules-and-tasks.
- **Line / child records:** Tasks (WBS, dates, duration, % complete, predecessors, resources, comments).
- **System-generated values:** Task IDs; schedule # default like 001; computed status from % complete vs today.
- **Files / attachments:** Print/export grid PDF/spreadsheet; not the same as Documentation linked files.
- **Audit / workflow fields:** Baseline vs scheduled dates; bulk reset IDs/baselines; prime contract dates can be set from schedule dates.

## Statuses and lifecycle

Task status is **computed** (not a free-typed enum on add):

| Status | Rule |
|---|---|
| Not Started | % complete = 0 and start date **after** today |
| Not Started - Delayed | % complete = 0 and start date **before** today |
| In Progress | 0 < % complete < 100 and finish **after** today |
| In Progress - Delayed | 0 < % complete < 100 and finish **before** today |
| Completed | % complete = 100 |

Successor-move logic: 100% complete → changing dates does not move successors; > 0% → start treated as fixed, finish/duration change prompts successor move; 0% → Sage asks whether to move successors.

## Dates that drive alerts

- Task **start date** (assigned and unassigned tasks).
- To-do **due date**.
- Scheduled (not baseline) dates drive Gantt and task calendars by default.

## Relationships

- **Upstream:** Feature Settings calendars; prime contract; directory; equipment; Excel / MS Project XML.
- **Downstream:** Email task notifications; TeamLink live Gantt; look-ahead print; set prime contract dates from schedule; daily log **Import Scheduling Activities**.
- **Sibling:** General/project To Dos (Scheduling resource center) — separate from Gantt tasks.

## Reports and exports

- Print grid / print grid to PDF / export grid to spreadsheet.
- Print or export a schedule; print or export a **look ahead** (# of weeks filter).
- Email assignments / task notifications to subcontractors and suppliers.
- View all active projects in Gantt style (cross-project).

## USIS / CM_Deploy mapping

USIS has installation **windows** (title + start/end + crew + assignee), not multi-schedule CPM/Gantt.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Scheduling Overview / calendars | none | none |
| Gantt + predecessors + baseline | none | none |
| Schedule item (window) | `project_schedule_items` | partial |
| Calendar events | `_calendar_service.py` `source_type=schedule_item` | partial |
| Project Schedule tab | `project-detail-schedule.js`, `project-detail.html` | partial |
| Task grid | `project-detail-tasks.js` | partial |
| Door/hardware schedules | door/hardware schedule pages | none (product schedules, not CPM) |
| TeamLink Gantt | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/ResourceCenter_Scheduling.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_Overview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_CollaborateOnLiveSchedule.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
- Local files reviewed
  - `backend/app/models/project_schedule.py`
  - `backend/app/api/_project_schedule_service.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/assets/js/project-detail-schedule.js`
