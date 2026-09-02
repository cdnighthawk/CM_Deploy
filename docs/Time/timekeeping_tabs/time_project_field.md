# Field → Time — project-strip mimic plan

**Route:** existing project-details page, child under Field  
**Sources:** BusyBusy has no project-chrome equivalent. Closest shots are Employees filtered by project, Map with Projects layer off, and project names inside Entries.  
**Parents:** `project_details_toolbar_cursor.md`, `timekeeping_web_busybusy_cursor.md` §3.2

## Job

The same clock, scoped to **this job**. Superintendents live here. Company Time → Live is the all-jobs board.

## What we do not invent

- A seventh project-strip parent.
- A BusyBusy Projects directory (GC-name list + clocked-in counts). USIS already has Project records.
- Construction schedule (Field → Schedule stays the job plan).
- Crew schedule.
- Cost-code live tracker for the job.

## Mimic (intent)

On Field → Time:

1. **Live on this job** — same roster columns as company Live, filtered `project_id = current`. KPI strip scoped too.
2. **Cards on this job** — period grid filtered to punches that touched this project. Totals are hours on *this* job, not the employee’s whole week (show both if they split days: “6.00 this job / 8.00 day”).
3. **Geofence editor** — circle (center + radius m) or polygon. Mode `flag` (default) or `block`. Reminder off / on_enter_leave (push copy only). Shift-end hour for `open_punch`. One `ProjectGeofence` row is source of truth.
4. **Hours this week vs estimate** — if `EstimateLineItem` exists for this project, a small panel of actual hours vs estimate. No BusyBusy all-time red budget bars. Optional cost-code split only when punches are tagged.

## Do not copy

- Treating GC name as the project key (Turner vs “UC Merced Medical Ed Building”). Use USIS project number + name.
- Embedding Map as the whole page. A compact “n on site” + Open Map (`/time/map?project=`) is enough.
- Shop/Office hours on a field job page.

## Acceptance

- Clock-in on this project appears here and on company Live.
- Geofence saved on Project is the fence the phone uses.
- Hours panel does not write into Estimating line items.
