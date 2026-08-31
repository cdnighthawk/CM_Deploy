# Schedules and tasks

Status: complete
Sage CM module: Scheduling
Official help: https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_Overview.htm

## Purpose

A **schedule** is a named Gantt (plus Resource, Calendar, Comments, Properties views) with unlimited tasks. Tasks have unique descriptions, WBS indent, scheduled vs baseline dates, duration (work days), % complete, FS/SS/FF/SF predecessors, and company/contact or equipment assignments. Users create manually, import Excel or Microsoft Project XML, or copy a schedule.

## Where it lives

- **Project Home** → Scheduling → **Schedules (Gantt Chart)** → schedule # or name.
- Create: Actions → **Add Schedule** (Task Creation = Manually, or import paths).
- Views: Gantt, Resource, Calendar (month + status), Comments, Properties.
- **Mobile:** Schedules and tasks R, E.
- **TeamLink:** live schedule; owners/architects read-only; vendors see assigned tasks only.

## Who uses it

- Scheduler/PM owns the Gantt and submits changes to server.
- Assigned contacts receive email notifications (contact **required** when assigning a company).
- Equipment dispatchers assign owned/rented equipment.
- Subs update via TeamLink (assigned rows) or emailed look-aheads.

## Prerequisites

- Project; **work Calendar** (Feature Settings → Scheduling).
- Optional prime contract (multiple lots/contracts).
- Unique **task descriptions** within a schedule (duplicate description → task **not saved**).
- Directory contact for company assignments; equipment records for equipment assignments.
- Save the schedule before Choose Bulk Actions if manual edits are pending.
- Allow popups for sagecm.intacct.com to print listings/calendars.

## What the user fills out

### Schedule header (Actions → Add Schedule)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | |
| Prime Contract | No | Prime contract | Recommended for design-build / multi-lot |
| Schedule # | No | Text | e.g. 001; user may update |
| Schedule Title | Yes | Text | |
| Comments | No | Text | |
| Calendar | Yes (help: select) | Work calendar | Work days and holidays |
| Task Creation | Yes | Choice | **Manually** (then Save & View); Excel and MS Project XML are separate create paths |

Properties view also shows project number, prime contract, schedule number, calendar.

### Task row (Gantt table — add row / add child / insert above)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Task description | Yes | Text | **Must be unique** in the schedule |
| Predecessor | No | Task ID syntax | See relationship types below |
| Task ID | Auto | Number | Used in predecessor references; bulk reset IDs by sort order |
| Indent / outdent | No | Hierarchy | Parent vs child (e.g. Sitework → Grade Site) |
| Scheduled start | Implied | Date | Default Gantt/calendar dates |
| Scheduled finish | Implied | Date | Milestone: no end date |
| Duration | Implied | Work days | 1 day = Mon 8AM–5PM; 2 days = Mon 8AM–Tue 5PM; **milestone duration = 0** |
| Baseline start / finish | No | Date | Set by copying scheduled dates (bulk) |
| Percent (%) complete | No | Number | 10% entered as 10; drives color and status |
| Resource (company/contact) | No | Directory | Contact required for email |
| Resource (equipment) | No | Equipment | Owned or rented |
| Comments | No | Text | Comments view lists tasks that have comments |

Toolbar: add row, add child, indent/outdent, expand/collapse, zoom, visible columns, show baseline, fix relationship issues, submit changes to server, filter tasks.

### Predecessor syntax (confirmed examples)

| Relationship | Example (predecessor ID 19) |
|---|---|
| Finish-to-Start, lag 0 | `19` |
| FS lag 2 | `19+2` |
| Start-to-Start lag 3 | `19SS+3` |
| Finish-to-Finish lag 1 | `19FF+1` |
| FS lead −2 | `19-2` |
| Multiple FS | `5;6;7` |

Types: FS (very common), SS, FF, SF (very rare).

### Filters (Gantt toolbar)

- Critical Tasks Only
- Look Ahead # of Weeks (used with printing)
- Not Assigned Tasks
- Status Filter: Not Started, In Progress, Completed
- All Tasks (clear filters)

### Bulk actions (save first)

- Assign company and contact resource
- Assign equipment item resource
- Update percent completed
- Clear assigned resources
- Reset baseline dates to scheduled dates (all tasks)
- Reset task IDs based on current sort order
- Set the prime contract dates based on the schedule dates

### Import / copy

- Import Microsoft Excel file
- Import Microsoft Project XML
- Copy a schedule  
Column maps for Excel/XML are **not confirmed in help** on the pages fetched.

## What Sage CM saves

- **Header record:** Schedule #, title, comments, calendar, prime contract, project.
- **Line / child records:** Tasks (unique description, ID, indent, scheduled/baseline dates, duration, % complete, predecessors, resources, comments).
- **System-generated values:** Task ID; computed status (see scheduling-overview); milestone = duration 0.
- **Files / attachments:** Export grid / PDF / look-ahead; TeamLink live chart (not a file).
- **Audit / workflow fields:** Submit changes to server; baseline snapshot; email assignments.

Two date sets: **baseline** (original plan) vs **scheduled** (default display).

## Statuses and lifecycle

See computed statuses in `scheduling-overview.md`. Open-item email: status **not Completed** and assigned to the selected company/contact.

Create paths: manual → add tasks; Excel; MS Project XML; copy.

## Dates that drive alerts

- Task **start date** (assigned and not assigned).
- Scheduled dates used by Gantt and calendars by default.

## Relationships

- **Upstream:** Calendar settings; prime contract; directory; equipment; Excel/XML.
- **Downstream:** Email notifications; TeamLink; look-ahead print; prime contract date sync; daily log import of scheduling activities.
- **USIS:** `project_schedule_items` is a flat window (title, start_date, end_date, crew_label, assignee_user_id, reminder_sent_on, sort_order) — no WBS, predecessors, % complete, or baseline.

## Reports and exports

- Print grid, PDF, spreadsheet export.
- Print/export schedule; look-ahead.
- Email task notifications.
- Collaborate on shared online schedule (TeamLink).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Schedule header (multi Gantt) | none | none |
| Task description / start / end | `project_schedule_items.title`, `start_date`, `end_date` | partial |
| Crew / assignee | `crew_label`, `assignee_user_id` | partial |
| Reminder sent | `reminder_sent_on` | stub |
| Sort order | `sort_order` | partial |
| API | `GET/POST/PATCH/DELETE /api/v1/projects/:id/schedule-items` | partial |
| UI | `project-detail-schedule.js`, `project-detail-tasks.js` | partial |
| Predecessors / % / baseline / calendar | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_Overview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_Add_Manually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_Function_AddingTasks.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/Schedules/Schedule_CollaborateOnLiveSchedule.htm
  - https://help.sagecm.intacct.com/Content/Modules/Scheduling/ResourceCenter_Scheduling.htm
- Local files reviewed
  - `backend/app/models/project_schedule.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/project-detail.html`
