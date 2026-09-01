# Cursor Implementation Brief — USIS CM Web Timekeeping (BusyBusy office side)

**Date:** 2026-09-01  
**Revised:** 2026-09-01 (live field clock mapping + QuickBooks **Desktop** on the office VM — agent sync, not QBO)  
**Repo:** `CM_Deploy`  
**Website product:** **USIS CM** (not FinishWorks)  
**Field companion:** FinishWorks Field — JSON contract is [`backend/API_FIELD.md`](../backend/API_FIELD.md) (Time clock section). Phone UX briefs live outside this repo; do not block on them.  
**Owner company:** US Interior Specialties — finish-work subcontractor, CA commercial + government

This ticket builds the **staff website** half of BusyBusy-style timekeeping. The phone already punches through `/api/v1/time-clock/*`. The office cannot approve, correct, job-cost, or export payroll from a phone. That is this module.

**This is an extension of the existing field clock, not a greenfield product.** `TimeEntry`, `TimePunch`, `CompanyCostCode`, project `CostCode` (`rfi_cost_codes`), and circle geofence on `Project` already ship. Alter those. Do not create a parallel `TimeEntry` / `CostCode` / punch API.

Mimic **BusyBusy’s office web app**, not its consumer brand, kiosk iPad, facial recognition, or equipment telematics.

---

## 0. Non-negotiable rules

- Keep xAI/Grok integration untouched. Do not dump time cards into Grok.
- Do **not** regress RFP, DrawingViewer, ChatBot, `aiReviewBus`, Estimating, Submittal QC, Material POs, correspondence archive, messenger.
- Staff UI is **W3CRM + Bootstrap 5 + DataTables + `usis-ui.css` LAST + `window.USISUi`**. Do **not** add React / MUI / DataGrid pages. Older encyclopedia pages that say `src/pages/*.tsx` are stale.
- Field time UX lives on the **native app**. Do not clone the giant CLOCK IN button as the website homepage. The web default is the **company operating view** (Who’s Working + exceptions + cards).
- Time clock ≠ T&M / PCO ticket. Payroll hours stay on the clock. T&M is a billing **copy** against a GC PCO number. Copying hours onto a T&M ticket must not remove or void the `TimeEntry`.
- Daily Report already exists (`DailyReport.sections.manpower`). Prefill that array from punches. Do not invent a second daily-log product inside Time.
- Photos already exist (`FieldPhoto`; `TimeEntry.clock_in_photo_id` / `clock_out_photo_id`; `TimePunch.photo_id`). Link. Do not build a second photo store.
- Do not build staff chat inside Time. Messenger already exists. Notify via existing SMTP + Celery + notification center (`HrmsNotification` + `_notifications.py`).
- Workflows are data. Seed `process_key = timecard` in `PROCESS_SEEDS` in [`backend/app/api/_workflow_service.py`](../backend/app/api/_workflow_service.py). Do not hardcode a private stepper. Subject grain is **per employee per period** (`HrmsTimesheetPeriod`), not the company pay-period row.
- In-flight pay periods freeze the definition version.
- No Jinja2 in frontend JS. Payroll CSV / timecard PDF = Flask + Jinja2 (`_document_render_service.py` + object storage). DIR / certified-payroll PDF is **not** v1.
- QuickBooks is **Desktop on the office VM**, not QuickBooks Online. Render (Linux) cannot open the company file. A **Windows agent on that VM** talks to QB via qbXML / QBFC (same idea as the Autodesk ingest PC + `CM_API_KEY`). Do **not** add Intuit OAuth or QBO TimeActivity. Do **not** copy I-9 / W-4 / SSN / bank data into QuickBooks.
- GPS is **verification**, not an automatic punch. Never auto clock-in on geofence enter. Never auto clock-out on leave. Never live-track people who are off the clock.
- **Reuse live models.** Do not invent a parallel employee table, cost-code table, or punch table. Field names stay `started_at` / `ended_at` / `client_id` — do not rename to `start_at` / `local_id` unless you migrate the phone.
- Shared mapping for phones: **extend** [`backend/API_FIELD.md`](../backend/API_FIELD.md). Same JSON shapes for Android and iOS. Keep the five POSTs. Do not replace them with `POST /api/time/punch`.
- California commercial + government work. Records must be defensible for payroll disputes, DIR / certified payroll later, and job cost.

---

## 1. What “mimic BusyBusy web” means

BusyBusy splits two surfaces:

| Surface | BusyBusy | USIS CM |
|---|---|---|
| Field | Giant Clock In, switch job/cost code, crew punch, offline, daily sign-off | Already live: `/api/v1/time-clock/*` + `API_FIELD.md` |
| Office web | Dashboard of who is working, time-card correction, payroll prep, map, budgets, settings | **This ticket** |

### Copy from BusyBusy web

1. **Live board** — who is clocked in, on break, clocked out; current job + cost code; hours today; GPS flag.
2. **Time-card grid** that looks like a paper card (employee × day, with regular / OT / DT). Click a cell → punch list for that day.
3. **Correction tools** — add, edit, split, void punches. Change project, cost code, start/end, unpaid meal. Full audit. Never hard-delete a punch after it is stored.
4. **Exception queue** — offsite punch, GPS denied, missing meal, missing sign-off, overlapping punches, open punch past shift end, clock skew.
5. **Employee + supervisor signatures** that lock the card. Payroll cannot export unsigned / unapproved rows (company setting, default ON).
6. **Payroll preparation** (not tax filing): pay-period totals, conflict scan, CSV download, and **queue hours for QuickBooks Desktop** after the period locks. Employees, jobs, and payroll items **sync from the company file on the office VM**. This app remains the clock. Do not replace it with QuickBooks Time (TSheets) or QBO.
7. **Map** (v1c) — project pins + people currently on the clock + selected employee breadcrumb for a date.
8. **Project geofence** editor (circle already exists; add polygon). Two modes: *block* outside (live default), or *allow and flag* (opt-in).
9. **Cost codes** as the second axis of job cost — **the existing company + project libraries**, not a new Time library.
10. **Web punch** exists, but buried on **My Time** — for shop / office / forgotten punch. Not the landing page. Calls the same `/api/v1/time-clock/*` endpoints.
11. **Job-cost rollup** (v1c) — hours and burden by project × cost code vs estimate / budget when `EstimateLineItem` / `CostCode.labor_hour_budget` exist.
12. CA overtime + meal **flags** computed on the server.

### Do not copy from BusyBusy

- Kiosk mode, facial recognition, PIN buddy-punch camera as v1.
- Equipment telematics / hour-meter / fuel as v1 (optional `equipment_id` column on `TimeEntry` is enough).
- BusyPayroll / tax filing / check print. Do not run QuickBooks Payroll, print checks, or file forms from this app.
- In-app team messenger (already a separate USIS CM module).
- Auto clock-in / auto clock-out from geofence.
- Off-clock live tracking.
- A 20-item left nav of modules we already have elsewhere (Documents, Daily Report, Photos, Scheduling CPM, Cost codes).
- Circle-only geofences if a polygon fits the site better — support both **in addition to** the live circle columns.
- Crow-flies “route” presented as the driven path. Store points; draw them as a polyline and label it “pings,” not “route.”
- A second CSI 09/10 cost-code seed that forks Admin → Cost codes.

---

## 2. Users and jobs-to-be-done (web)

| Role | Web jobs |
|---|---|
| Payroll / office admin | Correct cards, clear exceptions, lock period, export CSV, connect QuickBooks, match employees, push hours |
| Superintendent / field PM | Who’s on which job right now, approve crew cards, override geofence, punch a crew member who forgot |
| Project manager | Hours vs budget by cost code, offsite flags on *this* job |
| Foreman | Mostly on the phone. Web is approve + fix if they sit in the trailer |
| Journeyman | Rarely on web. **My Time** to see the week and sign if they use a browser |
| Director / President | Labor burn, OT, unsigned cards aging |

California rules that the **server** must compute (do not leave this to the phone). See §8 for the fixture table and combination algorithm.

- Daily OT after **8** hours, daily DT after **12**.
- Weekly OT after **40**.
- 7th consecutive day **in the defined workweek** (not any rolling 7 calendar days): first 8 at 1.5×, after 8 at 2×.
- Pay the method with the **greater weighted pay** (regular + 1.5× OT + 2× DT). Emit that method’s hour buckets. Do not mix daily and weekly buckets in one row.
- First unpaid meal: **must commence no later than the end of the 5th hour** of the shift (Wage Order 16 / LC 512). Not “after 5 hours.”
- First-meal waiver (v1): if total shift ≤ 6 hours and no meal punch, **do not** flag `missing_meal` (treat as waived).
- Second meal: required when the work period is more than 10 hours; must commence by the end of the 10th hour. Waiver (v1): if shift ≤ 12 hours **and** first meal was taken, do not flag a missing second meal. If shift > 12 hours and no second meal, flag.
- Paid rest: 10 min per 4 hours or major fraction thereof (major fraction ≥ 2 hours). Typical 8-hour shift = 2 rests. Crews usually do **not** clock 10-minute rests. Auto-flag `missing_rest` only when setting `track_rest_punches` is true (seed **false**). Manual `missing_rest` is always allowed.
- Missed meal / rest → **premium-hour flags that stack**. Each missed meal period is its own 1 hour at regular rate. Each missed rest period (when tracked) is its own 1 hour. A day with no first meal and no second meal (when the second is required) = two `missing_meal` flags. v1 **flags** only; payroll decides whether to pay. Do not silently add hours to `regular_hours`.
- Workweek start is a company setting (seed **Sunday 00:00** America/Los_Angeles). Project timezone on the Project record if present; else company timezone.

Prevailing-wage / DIR export is **not v1**. v1 still stores `classification` on `HrmsEmployeeProfile` so we do not reshape later.

---

## 3. Information architecture

### 3.1 Company-level (W3CRM left nav)

Nav is **static HTML**, not a menu table. Edit [`W3CRM-v3.0-13_September_2025/gulp/src/elements/deznav-construction.html`](../W3CRM-v3.0-13_September_2025/gulp/src/elements/deznav-construction.html) (and matching dist pages). Do not fork `deznav` styling.

Put timekeeping **under HR**, not a new left-nav parent. Staff look for time sheets next to Applications and HR suite.

**HR** children (existing + Time):

| Child | Gulp page | Purpose | Slice |
|---|---|---|---|
| HR dashboard | `usis-hr-dashboard.html` | Existing | — |
| Applications | `usis-hr-applications.html` | Existing | — |
| Time sheets | `construction/time-sheet.html` (until `usis-time-cards.html` ships) | Cards / hours | v1a landing |
| Live | `usis-time-live.html` | Who’s Working | v1a |
| Exceptions | `usis-time-exceptions.html` | Flag queue | v1a |
| My Time | `usis-time-me.html` | Self status + web punch | v1a |
| Payroll period | `usis-time-payroll.html` | Period lock + CSV + QuickBooks | v1b |
| QuickBooks | `usis-time-quickbooks.html` | VM agent, employee/job maps | v1b |
| Time settings | `usis-time-settings.html` | Policy, sign-off, geofence default | v1b |
| Map | `usis-time-map.html` | Clocked-in people + jobs | v1c |
| HR suite | `usis-hrms-home.html` | Existing | — |

v1a may ship **Time sheets** + **Live** + **Exceptions** + **My Time** as HR children. Do not add a top-level **Time** parent. Label is **Time sheets** (not “BusyBusy” or FinishWorks).

Gate new timekeeping children with `data-usis-module="hrms"` until a dedicated `time` module is granted in User admin (then `("time", "hrms")`).

**Do not** add Cost codes under HR. Admin → Cost codes remains the company library.

Copy src HTML/JS into dist if this repo patches dist directly. Do not `gulp-clean` dist.

### 3.2 Project-details strip

[`docs/project_details_toolbar_cursor.md`](project_details_toolbar_cursor.md) locked **seven** parents. Live UI labels the Field parent **Construction** (`data-usis-parent="field"` in `project-detail-tools-nav.js`).

**Do not invent an eighth parent.** Add Time as a **Construction child**:

```
Construction  →  Schedule (default)
                 Tasks
                 Photos
                 Daily log
                 Meetings
                 Work orders
                 QC
                 Punchlist
                 Incidents
                 Safety
                 Time          ← NEW child (this job only)
```

Wire `proj-tab-time` in `TAB_TO_PARENT` → `field`. Project Time = Live-on-this-job + cards filtered to this project + geofence editor + enabled project cost codes + (v1c) hours vs budget.

Geofence editor lives on the project (Job information **or** Construction → Time). One source of truth on `Project` columns (see §5).

### 3.3 My Time (individual)

`usis-time-me.html`

Clock status, week grid for the current user, sign-off, web punch. Office staff who never open the field app use this. Punches go through the **existing** field endpoints with `source` recorded as `web`.

---

## 4. Screens (web)

Stack each list as **DataTables** (same pattern as leads / estimates). Status via `USISUi.statusChip`. Empty via `USISUi.emptyState`. Primary `#1F4E5F`. Warning flags `#EAB308`. Danger `#EF4444`. Success `#22C55E`. Do not use W3CRM cyan. Filter persistence: same localStorage pattern as [`docs/table_autofilter_leads_estimates_cursor.md`](table_autofilter_leads_estimates_cursor.md).

### 4.1 Live / Who’s Working (`usis-time-live.html`)

Top KPI cards (company or current project if opened from the Construction strip):

- On the clock
- On break
- Open punches older than N hours (seed 12)
- Offsite / GPS flags today
- Unsigned days (trailing 7)
- Labor hours today / week

Main table columns:

`Employee | Status | Project | Cost code | Since | Elapsed | Last GPS | Accuracy | Flag | Actions`

Status chips: `In` / `Break` / `Out`. Elapsed uses existing `paid_seconds()` (shift minus break intervals).

Actions: View card, Map, Clock out (supervisor), Switch cost code (supervisor), Override geofence.

Supervisor actions punch **as that employee** (N rows, never one shared crew row) and must respect the live unique index: one non-closed `TimeEntry` per `user_id`. Set `punched_by_id` to the supervisor.

Auto-refresh every 30s when tab visible. No websocket required in v1 (polling is fine).

Empty: “Nobody is on the clock.”

### 4.2 Time cards (the paper-card grid)

Default view: current pay period, all clock-eligible employees, grouped by project filter.

Row = employee.  
Columns = Sun…Sat (or company week) + Regular + OT + DT + Premium flags + Sign + Approve.

Cell shows hours for that day (e.g. `8.00` / `8.00 + 1.50 OT`). Yellow dot if exceptions. Click cell → **Day drawer**.

**Day drawer**

- Punch timeline from `TimePunch` (clock_in, break_start/end, switch, clock_out) with project + cost code + GPS chip
- Computed regular / OT / DT / meal minutes (server numbers)
- Add punch / Edit / Split / Void
- Employee sign-off state (day + period)
- Supervisor approve / reject + comment
- Linked photos / notes (`clock_in_photo_id`, punch `photo_id`)
- Audit (“who changed what”)
- Action **Flag wrong project** — creates `flag_type = wrong_project` (manual; no auto-detect in v1)

**Split** = close the current `TimeEntry` at timestamp T and open a new one at T+≤1s on the new cost code (same as live `switch`). No gap larger than 1 second.

**Add punch** (office correction): require reason. Store `source = office_edit`, `punched_by_id`, reason on audit. GPS may be empty.

Locked rows (company period `locked` / `exported`) are read-only. Show “Reopen period” only to payroll admin.

Filters: employee, project, cost code, status (`open` / `signed` / `approved` / `locked` / `flagged`), date range.

CSV export of the visible grid (client-side of the DataTable is fine for the grid; payroll export is the Flask CSV in §4.4).

### 4.3 Exceptions

One queue. This is how payroll starts the morning.

Types (seed):

| `flag_type` | Meaning |
|---|---|
| `offsite` | Punch outside geofence when mode is `flag` |
| `blocked_override` | Supervisor overrode a `block` (today’s `override_geofence: true`) |
| `gps_denied` | Device had no fix / permission denied |
| `open_punch` | Still clocked in past shift-end rule |
| `overlap` | Two open intervals for one person (should be rare; unique index forbids two non-closed rows) |
| `missing_meal` | CA meal rule not met (one row per missed meal period) |
| `missing_rest` | CA rest rule not met (auto only if `track_rest_punches`; else manual) |
| `missing_signoff` | Day ended, no employee attest |
| `edited_after_sign` | Office edit after employee signed — needs re-sign |
| `cost_code_missing` | Required code not chosen |
| `clock_skew` | Device `occurred_at` vs server receive time differs by > 15 minutes |
| `wrong_project` | Manual flag from the day drawer |

Columns: When, Employee, Project, Type, Detail, Status (`open` / `accepted` / `corrected` / `dismissed`), Assignee.

Accept = keep the punch, clear flag, write reason.  
Correct = jump to day drawer.  
Dismiss = not a real issue, reason required.

### 4.4 Payroll period (`usis-time-payroll.html`) — v1b

List of **company** periods (weekly seed; biweekly later via setting).

Period detail:

- Headcount, regular / OT / DT hours, flagged rows still open
- **Pre-export scan** — cannot export if setting `block_export_with_open_flags` is true (seed true)
- Signatures remaining (count of `HrmsTimesheetPeriod` rows not signed / not approved)
- Table: employee, class, regular, OT, DT, PTO (show only if `HrmsLeaveRequest` hours fall in the period; else hide), per diem (hide if unused), projects touched
- Buttons: Lock period, Unlock (payroll admin), Export CSV, Print timecard PDF (Flask), **Queue for QuickBooks** (v1b — requires employee + job maps; agent on the VM writes Time Tracking)

CSV columns (seed, configurable later):

`employee_id, employee_name, classification, project_number, project_name, cost_code, date, time_in, time_out, meal_minutes, regular_hours, ot_hours, dt_hours, premium_hours, signed_at, approved_at`

CSV is the **fallback** (IIF-style download if the VM agent is down, or for ADP). The live path is Desktop Time Tracking via the agent (§4.10). This app is not a payroll engine. Do not calculate tax, net pay, or print checks.

Write the CSV and PDF into the Documents hub via existing `Document` + object storage. Link `TimecardPeriod.export_file_url` at that document. QB queue status lives on `TimecardPeriod` (`qb_status`, `qb_exported_at`) plus per-line `QbTimeExportLine`.

### 4.5 Map (`usis-time-map.html`) — v1c

**No Leaflet, Mapbox, or Google Maps JS SDK is in the repo today** (only Google embed iframes). Add **Leaflet + OSM**. Do not add a Google billing key.

Layers:

- Project geofence polygons / circles
- People currently on the clock (avatar + name + cost code). Click → Live row
- Selected employee + date breadcrumbs (points + time labels)

Off-clock people are **not** on the map.

### 4.6 Cost codes — reuse, do not rebuild

Company library = existing `CompanyCostCode` + [`usis-cost-codes.html`](../W3CRM-v3.0-13_September_2025/gulp/src/usis-cost-codes.html) + `GET/POST/PATCH /api/v1/cost-codes`.

Project job codes = existing `CostCode` (`rfi_cost_codes`). `TimeEntry.cost_code_id` already FKs this table. Field list: `GET /api/v1/projects/:id/cost-codes`. Cost code is already required on clock-in when the project has any active codes.

Do **not** seed a second CSI 09/10 list. If Travel / shop / dump / warranty / extra work / T&M are missing from `company_cost_codes`, **append those labor buckets** to the company library (non-CSI codes are fine) and sync to projects that need them.

Per project (on existing `CostCode` rows, add columns if missing): `required` (must pick on punch — live already requires *a* code when any exist), `favorite` (sort toward the top on the phone picker), `is_active` (already exists).

Do not store catalog SKUs here. Cost codes are labor / job-cost buckets, not the material import CSVs.

### 4.7 Project Time (Construction child)

Same Live table scoped to the project + geofence editor + enabled project codes + (v1c) hours-this-week by cost code vs `CostCode.labor_hour_budget` and matching `EstimateLineItem` CSI when present.

Geofence editor:

- Circle already: `Project.latitude`, `longitude`, `geofence_radius_m` (default 250)
- Add polygon (click map) stored as GeoJSON on `Project`
- Mode: `block` (**live default — keep it**) | `flag` (opt-in per project or company setting)
- Reminder: `off` | `on_enter_leave` (push copy only; field app sends the notification)
- Working hours window (for `open_punch` flag)

Changing company default from `block` to `flag` is a **phone behavior change**. Do not ship `flag` as the new default. Payroll may opt in per project.

**Missing GPS today:** `_check_geofence` treats missing lat/lon as outside → **409** unless `override_geofence`. Keep that in `block` mode. In `flag` mode: save the punch, set `gps_denied` (no coords) or `offsite` (coords outside), do not 409.

### 4.8 Settings (company) — v1b

Store policy as `HrmsModuleSetting` key `timekeeping` (JSON `value`). The Time Settings page and Company settings may both edit this key. Do not invent a third settings table. Amendable, not hardcoded.

```json
{
  "timezone": "America/Los_Angeles",
  "week_start": "sunday",
  "ot_daily_hours": 8,
  "dt_daily_hours": 12,
  "ot_weekly_hours": 40,
  "seventh_day_ot": true,
  "meal_must_start_by_hours": 5,
  "meal_minutes": 30,
  "meal_waive_if_shift_hours_lte": 6,
  "second_meal_after_hours": 10,
  "second_meal_waive_if_shift_hours_lte": 12,
  "rest_minutes_per_4h": 10,
  "track_rest_punches": false,
  "geofence_default_mode": "block",
  "require_cost_code": true,
  "require_daily_signoff": true,
  "require_supervisor_approve_before_export": true,
  "block_export_with_open_flags": true,
  "open_punch_flag_after_hours": 12,
  "web_punch_allowed": true,
  "breadcrumb_min_interval_sec": 180,
  "track_off_clock": false,
  "clock_skew_flag_minutes": 15,
  "qb_wage_item_regular": null,
  "qb_wage_item_ot": null,
  "qb_wage_item_dt": null,
  "qb_default_customer_list_id": null
}
```

Project may override geofence **mode**, polygon/circle, and required/favorite cost codes only.

### 4.9 My Time (`usis-time-me.html`)

Large status: In / Break / Out.  
If `web_punch_allowed`, show Clock In / Out / Break / Switch. Call existing `/api/v1/time-clock/clock-in` (etc.). Persist `source = web` on the entry/punch (new column). IP on audit. GPS only if the browser grants geolocation.

Week grid + sign today’s hours + sign period.

### 4.10 QuickBooks Desktop (office VM) — v1b

**Product fact:** USIS runs **QuickBooks Desktop** on a Windows VM on the company server (company file + Database Server Manager / RDP). The website on Render is Linux. COM / qbXML only works on that VM, with QuickBooks able to open the company file.

```
Payroll on website  →  queue jobs in USIS
Windows agent on QB VM  →  qbXML to Desktop  →  POST results back
```

Same shape as the Autodesk Desktop Connector ingest PC: a long-lived Bearer key, outbound HTTPS to `https://www.usiscm.com`, no inbound ports on the VM.

**Do not** implement QuickBooks Online OAuth, QBO TimeActivity, or QuickBooks Time (TSheets). `usis-hr-quickbooks-employee-reference.html` stays a field guide; the working UI is `usis-time-quickbooks.html`.

**Agent (on the VM)**

- Windows service or scheduled task next to QuickBooks. Python + QBFC/qbXML, or Intuit **Web Connector** (`.qwc`) pointed at USIS SOAP/qbXML **if** you prefer Intuit’s host — either is fine; USIS still owns the job queue.
- Auth: dedicated `QB_SYNC_API_KEY` (same Bearer style as `CM_API_KEY`). Do not reuse the ingest key in production.
- Needs: QuickBooks running (or Enterprise unattended company-file access), company file path, a QB user that can Time Tracking + Employee lists.
- Loop (every 1–5 min, or on Web Connector tick):
  1. `GET` pending employee-pull / mapping-refresh / time-export jobs
  2. Run `EmployeeQuery`, `CustomerQuery` (jobs), `ItemServiceQuery` / `PayrollItemWageQuery`, `TimeTrackingAdd`
  3. `POST` results (ListIDs, errors, TxnIDs)
- If QB is closed: job stays `queued`; website shows “Agent last seen … / QuickBooks not available.” Do not fail the pay-period lock.

**Website page (`usis-time-quickbooks.html`)**

Three blocks, DataTables, no dropdowns to other modules:

1. **Agent** — last heartbeat, QB company file name, last error. Copy install notes (env: `USIS_APP_PUBLIC_URL`, `QB_SYNC_API_KEY`, company-file path).
2. **Employees** — USIS user ↔ QB Employee `ListID`. Auto-match by email then exact name. Actions: Link, Unlink, **Pull from QuickBooks** (queues EmployeeQuery), **Create in QuickBooks** (queues `EmployeeAdd` with display name, email, hire date — **no SSN**). Unmatched QB people are **not** auto-created as USIS logins.
3. **Jobs and items** — `Project` ↔ QB Customer:Job `ListID`; earning types Regular / OT / DT ↔ `PayrollItemWage` (preferred) or Service Item `ListID`. Unmapped rows block **Queue for QuickBooks**, not CSV.

**Time export**

After period lock, payroll clicks **Queue for QuickBooks**. Preflight: every employee in the export has a `ListID`; every project has a Customer:Job `ListID` (or a company default “Overhead” job); Regular/OT/DT items mapped.

One `TimeTrackingAdd` per employee × date × job × earning type (regular, OT, DT as **separate** durations). Duration is ISO `PTnHnM` from server OT buckets, not raw punches. `BillableStatus` default NotBillable. Notes: cost code + USIS entry ids.

Idempotent: store QB `TxnID` on `QbTimeExportLine`. Re-queue skips lines that already have a TxnID unless payroll chooses Replace.

Premium-hour **flags** do not become Time Tracking rows unless payroll maps a wage item for them (default: omit; they stay on the CSV).

**IIF fallback:** same hour grid as CSV, TIMEREVT-style download, for a week the VM is down. Manual import in QuickBooks. Not the happy path.

---

## 5. Data model (SQLAlchemy) — extend, do not fork

**Source of truth for hours:** `TimeEntry` + `TimePunch`. The UI must not edit Regular/OT/DT cells without writing punches.

**Breaks are punch events, not rows.** Live model: one `TimeEntry` is a shift (job + cost code). `break_start` / `break_end` are `TimePunch.kind` values; `paid_seconds()` subtracts break intervals. Do **not** convert breaks into `TimeEntry` rows with `entry_type`. Travel / shop / dump are **cost codes**, not `entry_type`.

Never one shared row for a whole crew. Supervisor punch = N rows.

### 5.1 Already exists — keep names

| Class | Table | File | Role |
|---|---|---|---|
| `TimeEntry` | `time_entries` | `backend/app/models/field_ops.py` | One shift segment. Unique `client_id`. Partial unique: one non-closed row per `user_id`. FK `cost_code_id` → `rfi_cost_codes.id`. Photos: `clock_in_photo_id`, `clock_out_photo_id`. |
| `TimePunch` | `time_punches` | same | Immutable clock event: `kind` in `clock_in` / `clock_out` / `break_start` / `break_end` / `switch`. `occurred_at`, lat/lon/`accuracy_m`, `geofence_ok`, `geofence_distance_m`, `client_id`. **This is the event log.** Do not create `TimePunchEvent`. |
| `CompanyCostCode` | `company_cost_codes` | `backend/app/models/company_cost_code.py` | Firm-wide CSI library. |
| `CostCode` | `rfi_cost_codes` | `backend/app/models/rfi_lookups.py` | Per-project job codes. |
| `Project` | `projects` | `backend/app/models/project.py` | `latitude`, `longitude`, `geofence_radius_m` (default 250). Circle fence lives here. |
| `User` | `users` | `backend/app/models/auth.py` | Worker. Do not duplicate. |
| `HrmsEmployeeProfile` | `hrms_employee_profiles` | `backend/app/models/hrms_core.py` | 1:1 user HR extension (`hire_date`, `manager_user_id`, `job_title`). |
| `HrEmployeePayScale` | `hr_employee_pay_scales` | `backend/app/models/hr.py` | `hourly_rate`, `wage_rate_id`. Job-cost dollars. Do not show rates on the phone. |
| `WageRate` | `wage_rates` | `backend/app/models/wage_rate.py` | Prevailing-wage reference. |
| `HrmsTimesheetPeriod` | `hrms_timesheet_periods` | `hrms_core.py` | **Per-user** period card. Unique `(user_id, period_start)`. |
| `HrmsTimesheetEntry` | `hrms_timesheet_entries` | same | Per-day hours on that card; already has `time_entry_id`, `project_id`, `cost_code_id`. |
| `HrmsModuleSetting` | `hrms_module_settings` | same | JSON policy store. Key `timekeeping`. |
| `HrmsLeaveRequest` | `hrms_leave_requests` | same | PTO for payroll table (hide column if unused). |
| `DailyReport` | `daily_reports` | `field_ops.py` | `sections.manpower` array. |
| `FieldPhoto` | `field_photos` | same | Punch photos. |
| `ProjectMember` | `project_members` | `backend/app/models/project_member.py` | Crew RBAC: who is on which job. |
| `AuditLog` | `audit_log` | `backend/app/models/audit.py` | Office edit `before` / `after` JSON + reason in `changes` / `message`. |
| `EstimateLineItem` | estimate lines | `backend/app/models/estimate.py` | v1c hours vs budget. |
| `Document` | `documents` | `backend/app/models/document.py` | Export file. |

Live field names (do not rename):

- `TimeEntry.started_at` / `ended_at` / `status` (`open` / `on_break` / `closed`) / `client_id`
- `TimePunch.occurred_at` / `kind` / `client_id`
- Idempotency key is **`client_id`**. Accept `local_id` as an alias in JSON only if you must; persist `client_id`.

### 5.2 Alter existing columns

**`TimeEntry` — add, do not rename**

- `source` — `mobile` / `supervisor_mobile` / `web` / `office_edit` (kiosk unused)
- `punched_by_id` — who tapped (supervisor vs self); default `user_id`
- `device_started_at` / `device_ended_at` — phone clock; `started_at` remains the value used for math (see §7: server receives both)
- `gps_status` — `ok` / `denied` / `unavailable` / `stale` (nullable; infer from punch coords when absent)
- `locked` — bool after company period lock/export
- `voided_at` / `void_reason` / `voided_by_id` — never hard-delete after a punch exists
- `equipment_id` — nullable UUID, no FK required in v1
- `edit_reason` — last office reason (full history is `AuditLog`)

**`TimePunch` — append-only**

- Remove `cascade="all, delete-orphan"` (or stop deleting punches when voiding an entry). Void the `TimeEntry`; keep punches.
- Add `source`, `punched_by_id`, `server_received_at` (set on insert; used for `clock_skew`).
- Do not add breadcrumb kinds here.

**`Project` — extend the live circle**

- `geofence_mode` — `block` (default, matches live 409) \| `flag`
- `geofence_shape` — `circle` (default) \| `polygon`
- `geofence_polygon` — JSONB GeoJSON, nullable
- `geofence_reminder_mode` — `off` \| `on_enter_leave`
- `shift_end_hour` — nullable int, local hour for `open_punch`
- `qb_customer_list_id` — Customer:Job `ListID` in the Desktop company file

Keep `latitude` / `longitude` / `geofence_radius_m` as the circle. Do not create `ProjectGeofence` unless a project needs **multiple** fences (v1 = one fence per project on `Project`).

**`CostCode` (project)**

- `favorite` bool, default false
- `required` bool, default false (project-level “must pick this family” is optional; live already requires some active code)

**`HrmsEmployeeProfile` — not a new `EmployeeTimeProfile`**

- `classification` (string, DIR class later)
- `union_local`
- `prevailing_class`
- `default_cost_code_id` (nullable, company or project code — prefer company code id if you only store one)
- `is_clock_eligible` bool, default true
- `qb_list_id` — QuickBooks Desktop Employee `ListID` (empty until matched)
- `qb_edit_sequence` — last `EditSequence` from EmployeeQuery (needed for `EmployeeMod`)
- `qb_name` — snapshot of QB Name for mismatch warnings
- Rates stay on `HrEmployeePayScale` (`hourly_rate`) + optional `burden_rate` column there or a numeric on the profile. **Do not add a third rate table.**

**`HrmsTimesheetPeriod` — this is the employee card (do not create `TimecardPeriodEmployee`)**

- `company_period_id` → `TimecardPeriod.id` (nullable until the company week is materialized)
- `regular_hours` / `ot_hours` / `dt_hours` / `premium_hours` (denorm totals)
- `signed_at` / `signed_ip` / `signature_png_url`
- `approved_at` / `approved_by_id`
- `workflow_instance_id` — **this** is the workflow subject
- Existing `status` / `approver_user_id` / `decided_at` stay; map `draft` → unsigned, extend statuses as needed (`signed` / `approved` / `locked`) rather than forking a new table.

**`HrmsTimesheetEntry` — sync from punches, do not be a second clock**

- Add `regular_hours`, `ot_hours`, `dt_hours`, `premium_hours`, `meal_minutes`.
- `hours_worked` = paid hours (`paid_seconds()/3600`), **not** gross `ended_at - started_at`.
- Recompute when punches change. Convert-clock (`POST /me/timesheets/convert-clock` in `_wave2_service.py`) **must** call `paid_seconds()` in the same change set as the OT engine. Today it uses gross elapsed and ignores breaks — that is a bug.

### 5.3 New tables

**`TimecardDay`** — denormalized per user per local date (company/project timezone):

`user_id, work_date, regular_hours, ot_hours, dt_hours, premium_hours, meal_minutes, signed_at, signed_ip, signature_png_url, employee_attested_accurate, injury_reported, injury_note`

Recompute from `TimeEntry` + `TimePunch` when punches change. Daily sign-off lives here. This is **not** the workflow subject.

**`TimecardPeriod`** — **company-wide** pay week (lock + export only):

`id, period_start, period_end, status (open / reviewing / locked / exported), exported_at, exported_by, export_file_url, qb_status (idle / queued / syncing / synced / error), qb_exported_at, qb_error`

No `workflow_instance_id` on this row. Locking is a payroll-admin action that requires employee cards in range to be approved when `require_supervisor_approve_before_export` is on. CSV export and QB queue are independent: a period can be CSV-exported, QB-queued, or both.

**`TimeFlag`**

`id, user_id, time_entry_id nullable, punch_id nullable, project_id, flag_type, status, detail, assigned_to, resolved_by, resolved_at, reason`

**`TimeBreadcrumb`**

`id, user_id, project_id, time_entry_id, at, lat, lon, acc` — only while clocked in. Purge policy later; keep ≥ 90 days.

**`QbSyncJob`** — work for the VM agent (append-only until complete):

`id, kind (employee_pull / employee_add / mapping_pull / time_export), status (queued / running / done / error), payload_json, result_json, period_id nullable, created_at, started_at, finished_at, error`

**`QbRef`** — cached Desktop lists for the mapping UI:

`kind (employee / customer_job / payroll_wage_item / service_item), list_id, name, is_active, extra_json, pulled_at`

**`QbTimeExportLine`** — one Time Tracking txn (or IIF row):

`id, period_id, user_id, work_date, project_id, cost_code_id, earning_type (regular / ot / dt / premium), hours, qb_txn_id nullable, status (pending / written / skipped / error), error`

Company wage-item maps (regular / ot / dt ListIDs) live on `HrmsModuleSetting` key `timekeeping` (`qb_wage_item_regular`, `qb_wage_item_ot`, `qb_wage_item_dt`).

### 5.4 Period model (locked decision)

```
TimecardPeriod          company week          lock / CSV / PDF
        │
        └── HrmsTimesheetPeriod   per employee     sign / approve / workflow
                    │
                    ├── HrmsTimesheetEntry        per day hours (synced)
                    ├── TimecardDay               per day sign + OT buckets
                    └── TimeEntry + TimePunch     source of truth
```

- Do **not** create `TimecardPeriodEmployee`.
- Do **not** replace `HrmsTimesheetPeriod`.
- Convert-clock becomes “recompute this user’s period from punches” using `paid_seconds()` + §8.

### 5.5 Audit

Every office add / edit / split / void writes `AuditLog` with `entity_type` `TimeEntry` or `TimePunch`, `changes: {before, after, reason}`.

---

## 6. Workflow (`process_key = timecard`)

Seed in `PROCESS_SEEDS` inside [`backend/app/api/_workflow_service.py`](../backend/app/api/_workflow_service.py) via `ensure_default_definition`. Queues: at least `payroll`.

**Subject:** `subject_type = hrms_timesheet_period`, `subject_id = HrmsTimesheetPeriod.id`. One instance per employee per week.

Day attest (`TimecardDay.signed_at`) is **not** a workflow step. Period employee sign/approve are.

Seed definition (amendable):

| step_key | label | who |
|---|---|---|
| `capture` | Punches recorded | system (auto-complete when the period exists) |
| `employee_sign` | Employee attests the period | worker (self) |
| `supervisor_approve` | Field supervisor | `ProjectMember` on a project the employee worked that week, or `HrmsEmployeeProfile.manager_user_id` |
| `payroll_lock` | Visible on the card when the **company** `TimecardPeriod` locks | queue Payroll (system/admin) |
| `exported` | Company CSV generated | system |

Rules:

- Edit after `employee_sign` → void that period’s signature **and** any `TimecardDay` signatures touched by the edit, set `edited_after_sign`, require re-sign.
- Edit after company period `locked` → blocked unless payroll admin reopens `TimecardPeriod`.
- T&M ticket signatures do **not** satisfy this workflow.
- In-flight periods freeze definition version.

Notify with existing notification + email. No chat.

---

## 7. API (Flask) — extend the live field family

**Do not add `/api/time`.** All time-clock traffic stays under `/api/v1/time-clock/` (and existing project geofence fields on `Project`). Update [`backend/API_FIELD.md`](../backend/API_FIELD.md) in the same PR as new routes.

Idempotent writes: client sends `client_id` (UUID). Duplicate `client_id` returns the existing row. Optional JSON alias: `local_id` → `client_id`.

### Already live — keep (field + My Time)

Documented in `API_FIELD.md`:

```
GET  /api/v1/time-clock/me
POST /api/v1/time-clock/clock-in
POST /api/v1/time-clock/clock-out
POST /api/v1/time-clock/break-start
POST /api/v1/time-clock/break-end
POST /api/v1/time-clock/switch
GET  /api/v1/projects/:id/cost-codes
```

Bodies stay as today (`project_id`, `entry_id`, `cost_code_id`, `occurred_at`, `lat`, `lon`, `accuracy_m`, `note`, `client_id`, `new_entry_client_id`, `photo_id`, `override_geofence`). Add optional `source` (`mobile` default).

### Add — field + web

```
GET    /api/v1/time-clock/live
GET    /api/v1/time-clock/entries          filters
GET    /api/v1/time-clock/entries/:id
PATCH  /api/v1/time-clock/entries/:id      office correction (reason required)
POST   /api/v1/time-clock/entries          manual add (reason required)
POST   /api/v1/time-clock/entries/:id/split   { at, cost_code_id?, project_id?, client_id, new_entry_client_id }
POST   /api/v1/time-clock/entries/:id/void    { reason }   — never hard-delete after lock; void
POST   /api/v1/time-clock/breadcrumbs      batch (clocked-in only)
POST   /api/v1/time-clock/days/:date/sign     { signature_png, attested, injury, note }
POST   /api/v1/time-clock/periods/:id/sign     → HrmsTimesheetPeriod.id
POST   /api/v1/time-clock/periods/:id/approve
GET    /api/v1/projects/:id/geofence       reads Project fence fields
PATCH  /api/v1/projects/:id/geofence       office editor (RBAC)
```

### Add — web only

```
GET    /api/v1/time-clock/flags
POST   /api/v1/time-clock/flags/:id/accept
POST   /api/v1/time-clock/flags/:id/dismiss
POST   /api/v1/time-clock/flags            { flag_type: wrong_project, ... }
GET    /api/v1/time-clock/company-periods
POST   /api/v1/time-clock/company-periods/:id/lock
POST   /api/v1/time-clock/company-periods/:id/export   → CSV in Documents hub + download
POST   /api/v1/time-clock/company-periods/:id/queue-quickbooks
GET    /api/v1/time-clock/job-cost?project_id=&from=&to=
GET    /api/v1/time-clock/settings
PATCH  /api/v1/time-clock/settings         HrmsModuleSetting key timekeeping
GET    /api/v1/time-clock/quickbooks
POST   /api/v1/time-clock/quickbooks/employees/:user_id/link   { list_id }
POST   /api/v1/time-clock/quickbooks/jobs/:project_id/link     { list_id }
```

QB VM agent (Bearer `QB_SYNC_API_KEY`, same style as ingest — **not** the staff cookie). Exempt from module ACL like other ingest keys, or map prefix `/api/v1/integrations/quickbooks` to a dedicated rule:

```
POST /api/v1/integrations/quickbooks/heartbeat     { company_file, qb_version }
GET  /api/v1/integrations/quickbooks/jobs          next queued QbSyncJob
POST /api/v1/integrations/quickbooks/jobs/:id/ack
POST /api/v1/integrations/quickbooks/employees     EmployeeQuery payload (upsert QbRef + suggest matches)
POST /api/v1/integrations/quickbooks/customers     Customer:Job list
POST /api/v1/integrations/quickbooks/wage-items
POST /api/v1/integrations/quickbooks/time-results  TxnIDs / errors per QbTimeExportLine
```

Cost-code CRUD stays on `/api/v1/cost-codes` and `/api/v1/projects/:id/cost-codes`. Do not duplicate.

### Module ACL

Today [`backend/app/api/_module_routes.py`](../backend/app/api/_module_routes.py) maps `/api/v1/time-clock` → `projects`. Payroll users may lack the projects module.

- Add module code `time`.
- Map `/api/v1/time-clock` → `("time", "projects")` so the field app keeps working and payroll can be granted `time` only.
- Gate new deznav items with `data-usis-module="time"`.

### RBAC

No separate crew table in v1.

- **Worker:** self only + sign self. `HrmsEmployeeProfile.is_clock_eligible`.
- **Foreman / superintendent:** users who share a `ProjectMember` row on a project the worker punched that day/week, **or** are `manager_user_id` on the worker’s profile. Approve, live, correct with reason, supervisor punch, geofence override.
- **Payroll / admin:** all, lock, export, reopen, settings, QuickBooks maps, queue QB export.
- **PM:** `ProjectMember` on that project — read + job cost + exceptions for that job.

409 if:

- `geofence_mode = block` and device outside (unless `override_geofence` + role)
- Editing a locked row
- Clock-in without cost code when the project has active codes (live rule) or company `require_cost_code`
- Duplicate open work entry for user (live unique index)

**Server time vs device time.** Payroll math uses `TimeEntry.started_at` / `ended_at` and `TimePunch.occurred_at` as stored. On insert, set `server_received_at = now(UTC)`. If `occurred_at` is missing, use server now (live `_occurred_at` already does this). If both present and skew > `clock_skew_flag_minutes` (15), add flag `clock_skew`. Do not silently rewrite `occurred_at` unless it is unparseable.

Offline field: queue FIFO. Server applies in `occurred_at` order per user (already implied by `client_id` replay).

---

## 8. Overtime / break engine (server)

Pure functions in [`backend/app/api/_time_clock_math.py`](../backend/app/api/_time_clock_math.py) (extend; keep `paid_seconds` and `evaluate_geofence`). Unit-tested. Do not implement this only in JS. Phone may show a preview; export uses server numbers.

```
paid_seconds(started_at, ended_at, punches, now)     # already exists
compute_day(entries, punches, policy) ->
    { regular, ot, dt, meal_minutes, meal_ok, rest_ok, premium_flags[] }
compute_week(days, policy) ->
    winning { regular, ot, dt } using greater weighted pay
```

`premium_flags[]` is a list of `{flag_type, detail}` — one item per missed meal period (and rest if tracked). Stacking is required.

### Meal detection

An unpaid break is a `break_start`→`break_end` pair whose duration ≥ `meal_minutes`.

- First meal **ok** if a qualifying break **commences at or before** `meal_must_start_by_hours` (5.0) from `TimeEntry.started_at` of the first segment that day (shift start).
- Skip `missing_meal` when total paid+unpaid shift length ≤ `meal_waive_if_shift_hours_lte` (6) and no first meal was taken.
- Second meal required when shift length > `second_meal_after_hours` (10). Must commence by hour 10. Skip the second-meal flag when shift ≤ `second_meal_waive_if_shift_hours_lte` (12) **and** first meal was taken.
- If the worker never tapped break but was on the clock through the rule, flag. Office can insert a meal punch (`break_start`/`break_end`).

### Greater-of combination (do not mix buckets)

1. Compute **daily method** hour buckets for the workweek (daily OT after 8, DT after 12; 7th-day premiums apply on the 7th consecutive worked day in the workweek).
2. Compute **weekly method** hour buckets (first 40 regular, then OT; DT still applies after 12 in a day if policy `dt_daily_hours` is on — weekly method does not erase daily DT).
3. Weighted pay units = `regular + 1.5 * ot + 2.0 * dt` (premium flags are **outside** this comparison; they stay flags).
4. Emit the method with the greater weighted pay. On a tie, emit daily (more familiar on a paper card).
5. Never output 40 regular from weekly plus extra daily OT on top.

### Fixture table (must appear as unit tests)

Assume workweek Sunday–Saturday, no 7th-day unless noted, meal taken, no premiums in the hour buckets.

| Case | Pattern | Daily buckets | Weekly buckets | Winner (hours emitted) |
|---|---|---|---|---|
| A | 5 × 8h | 40 R | 40 R | 40 R (tie → daily) |
| B | 5 × 10h | 40 R + 10 OT | 40 R + 10 OT | 40 R + 10 OT (tie → daily) |
| C | 4 × 11h | 32 R + 12 OT | 40 R + 4 OT | **32 R + 12 OT** (daily weighted 32+18=50 > 40+6=46) |
| D | 1 × 13h | 8 R + 4 OT + 1 DT | 8 R + 5 OT | **8 R + 4 OT + 1 DT** (daily 8+6+2=16 > 8+7.5=15.5) |
| E | 7 consecutive days × 8h (7th-day rule on) | 48 R + 8 OT (days 1–6 regular; day 7 all 1.5×). Weighted 60 | 40 R + 16 OT (56h − 40). Weighted 64 | **40 R + 16 OT** (weekly). Do not also emit 7th-day OT on top |
| F | Shift 5.5h, no meal punch | hours as worked; **no** `missing_meal` (waiver ≤6) | — | — |
| G | Shift 8h, no meal punch | hours as worked; **one** `missing_meal`; `premium_hours` flag 1 (not added to regular) | — | — |
| H | Shift 12.5h, first meal only | **one** `missing_meal` (second required; no waiver because >12) | — | — |

---

## 9. Feeds to other modules

| From Time | To |
|---|---|
| Day punches | Daily Report Manpower prefill (see object below) |
| Selected people/hours | T&M ticket “Add from today’s punches” — **copy**, do not move or void `TimeEntry` |
| Hours × burden (`HrEmployeePayScale`) | Job costing on Contract parent, or a panel on Project Time (v1c) |
| Actual hours by CSI | Estimating later (do not rebuild Estimating in this ticket) |
| Who’s Working count | Project Overview widget (web + field) |
| Signed PDF | Documents hub under the project / employee |
| Locked period hours | QuickBooks Desktop Time Tracking via the office VM agent (`TimeTrackingAdd`) |
| Clock-eligible users | QB Employee list on the VM (pull/match; optional `EmployeeAdd`) |

Do not write Time hours into Material PO, RFP, or submittal records. Do not write hours into QuickBooks from Render — only the VM agent does.

**Manpower prefill object** — write into `DailyReport.sections.manpower` (array). Today the UI accepts `{ notes }` or `{ company, count, notes }`. Prefill **one row per trade (cost-code division)**:

```json
{
  "company": "US Interior Specialties",
  "trade": "<CostCode.division_desc or code>",
  "count": 3,
  "hours": 24.0,
  "notes": "<employee display names>",
  "user_ids": ["<uuid>", "<uuid>", "<uuid>"]
}
```

`hours` is paid hours that day on that project/trade (`paid_seconds` summed). Do not overwrite a manpower array the superintendent already edited; offer a “Prefill from punches” action that fills only when the array is empty **or** the user confirms replace.

---

## 10. Local AI (optional, do not block v1)

Reuse ChatBot + `aiReviewBus`. New mode only: `time_exception_review`.

Purple button on Exceptions: “Review flags with Local AI.” Payload = flag rows + punch timeline (no live GPS stream). Output = suggested accept vs correct + short reason. Human still clicks Accept/Correct.

Default provider Local Llama 4 Scout. Grok remains available and untouched.

If this takes more than a half day, ship without it. Not in v1a.

---

## 11. Implementation order (Cursor)

Do not start with scheduling, kiosk, DIR XML, equipment GPS, or a new punch API.

### v1a — office board on the live clock

1. Document the mapping in [`backend/API_FIELD.md`](../backend/API_FIELD.md) (this brief is the map; keep the field JSON section in sync as you add routes).
2. **Alter** `TimeEntry`, `TimePunch`, `Project`, `HrmsEmployeeProfile`, `CostCode` as in §5. Add `TimeFlag`, `TimecardDay`, `TimeBreadcrumb`. **Do not** create `CostCode` / `TimeEntry` / `TimePunchEvent` / `ProjectGeofence` / `EmployeeTimeProfile` as new parallel types.
3. Extend `_time_clock_math.py` with `compute_day` / `compute_week` + the fixture table. Fix convert-clock to `paid_seconds()`. Keep live geofence **block** default; add `flag` mode as opt-in.
4. Add office/live/entries/split/void/flags routes under `/api/v1/time-clock/`. Keep `client_id`. Module ACL `("time", "projects")`.
5. Web Live page (`usis-time-live.html`, DataTables + 30s poll). **HR → Time sheets** (and Live / Exceptions / My Time) in `deznav-construction.html` — not a new Time parent.
6. Time cards grid + day drawer (add/edit/split/void + audit).
7. Exceptions queue (including `clock_skew`, `wrong_project` action).
8. My Time web punch via existing five POSTs + `source=web`.
9. Construction → Time child on the project-details strip (`proj-tab-time`).

### v1b — sign-off, workflow, payroll

10. Daily + period sign-off fields. Seed `timecard` in `PROCESS_SEEDS` on `HrmsTimesheetPeriod`.
11. `TimecardPeriod` company week + lock + CSV/PDF into Documents hub. Settings page writes `HrmsModuleSetting` key `timekeeping`.
12. Append missing labor buckets (Travel / shop / dump / warranty / extra / T&M) to `CompanyCostCode` **if absent**. Link Time Settings → existing Cost codes page.
13. QuickBooks Desktop: `QbSyncJob` / `QbRef` / `QbTimeExportLine`, agent Bearer routes, `usis-time-quickbooks.html`, period **Queue for QuickBooks**. Ship a Windows agent script under `backend/scripts/qb_desktop_agent/` (heartbeat + job loop + qbXML). Document install on the QB VM in the same PR (`QB_SYNC_API_KEY` on Render).

### v1c — map, daily log, job cost

14. Leaflet + OSM map + polygon geofence editor on `Project`. Breadcrumbs.
15. Daily Report manpower prefill action (§9 object).
16. Job-cost hours panel on Project Time (read `CostCode.labor_hour_budget` / `EstimateLineItem` if present).

---

## 12. What v1 does **not** include

- Kiosk / face match / PIN camera
- Equipment telematics
- Payroll tax, net pay, printed checks, ADP live connector (CSV only)
- QuickBooks **Online** / Intuit OAuth / QBO TimeActivity / QuickBooks Time (TSheets). Desktop on the office VM only.
- Opening the company file from Render or any Linux process
- DIR eCPR / WH-347 certified payroll (store `classification` on `HrmsEmployeeProfile`; build export later)
- Auto geofence punches
- Off-clock tracking
- Full crew scheduling / shift planner (`HrmsShift` stays unused by this ticket)
- Materials inside Time
- Staff messenger (already a separate module; do not rebuild it here)
- React / MUI rewrite
- Changing field-app stack (Kotlin / Compose / Room still stands)
- Replacing `/api/v1/time-clock/clock-in` with a single `POST /api/time/punch`
- A second company cost-code library
- Shipping geofence default `flag` (would 409→save overnight on the phone)

v1a may ship without v1b/v1c.

---

## 13. Acceptance checks

- Worker clocks in on the phone via **existing** `/api/v1/time-clock/clock-in` + `client_id`; Live page shows them within one poll.
- Switch cost code on phone creates two `TimeEntry` rows with ≤ 1s gap (live `switch` behavior unchanged).
- Outside geofence + mode `block` (default) → 409 unless supervisor override (`blocked_override` flag when they override). Mode `flag` → punch saved + Exceptions row (`offsite`).
- Missing GPS + mode `block` → 409 (live). Missing GPS + mode `flag` → saved + `gps_denied`.
- Off-clock user never appears on Map (v1c).
- Office split of a 10-hour punch at hour 6 onto a new cost code recomputes OT on the server (fixture-adjacent).
- Fixture cases A–D and F–H pass as unit tests. Case E emits **40 R + 16 OT** (weekly greater than 7th-day daily).
- Employee sign, then office edit → signature cleared, `edited_after_sign` flag, cannot export until re-signed (when setting on) — v1b.
- Period with open `missing_meal` flags cannot export when `block_export_with_open_flags` is true — v1b.
- Queue for QuickBooks refuses the period if any exported employee or job lacks a Desktop `ListID`; CSV still downloads — v1b.
- VM agent with `QB_SYNC_API_KEY` pulls a `time_export` job, writes `TimeTrackingAdd`, posts TxnIDs; website shows `qb_status = synced`. Repeat queue does not duplicate TxnIDs — v1b.
- Pull from QuickBooks upserts `QbRef` employees; Link stores `HrmsEmployeeProfile.qb_list_id`. Create-in-QB does not send SSN — v1b.
- Convert-clock / `HrmsTimesheetEntry.hours_worked` equals `paid_seconds` (breaks excluded), not gross elapsed.
- T&M ticket hours do not disappear from the timecard.
- Daily Report manpower can be prefilled with the §9 object from the same day’s punches — v1c.
- `usis-ui.css` still last. No cyan regression. No new React app.
- Grok ChatBot still streams. RFP public portal still quotes. Messenger still opens.
- Android and iOS still hit the same five punch POSTs. No `/api/time/punch`.
- Admin → Cost codes still owns the library. Time sheets live under **HR**, not a duplicate Cost codes child.

---

## 14. Related files (read before coding)

These exist in **this** repo. Do not stall on missing encyclopedia briefs.

| File | Why |
|---|---|
| [`backend/API_FIELD.md`](../backend/API_FIELD.md) | Live punch JSON, `client_id`, geofence 409, cost-code rule |
| [`backend/app/models/field_ops.py`](../backend/app/models/field_ops.py) | `TimeEntry`, `TimePunch`, `DailyReport`, `FieldPhoto` |
| [`backend/app/api/_time_clock_service.py`](../backend/app/api/_time_clock_service.py) | Clock in/out/break/switch |
| [`backend/app/api/_time_clock_math.py`](../backend/app/api/_time_clock_math.py) | `paid_seconds`, circle geofence |
| [`backend/tests/test_field_time_clock.py`](../backend/tests/test_field_time_clock.py) | Do not break these |
| [`backend/app/models/company_cost_code.py`](../backend/app/models/company_cost_code.py) | Company library |
| [`backend/app/models/rfi_lookups.py`](../backend/app/models/rfi_lookups.py) | Project `CostCode` |
| [`backend/app/models/hrms_core.py`](../backend/app/models/hrms_core.py) | Profile, timesheet period/entry, `HrmsModuleSetting` |
| [`backend/app/models/hr.py`](../backend/app/models/hr.py) | `HrEmployeePayScale` |
| [`backend/app/api/_workflow_service.py`](../backend/app/api/_workflow_service.py) | `PROCESS_SEEDS` — add `timecard` |
| [`backend/app/api/_module_routes.py`](../backend/app/api/_module_routes.py) | ACL prefixes |
| [`docs/project_details_toolbar_cursor.md`](project_details_toolbar_cursor.md) | Seven parents; Construction/Field children |
| [`docs/ui_consistency_modernization_cursor.md`](ui_consistency_modernization_cursor.md) | W3CRM tokens, pin order |
| [`backend/app/api/ingest.py`](../backend/app/api/ingest.py) | Bearer-key agent pattern to copy for `QB_SYNC_API_KEY` |
| [`docs/render-deploy.md`](render-deploy.md) | `CM_API_KEY` / Render secrets — add `QB_SYNC_API_KEY` the same way |

Website product name is **USIS CM**. Field product name is **FinishWorks Field**. Do not title this module FinishWorks on the staff site.
