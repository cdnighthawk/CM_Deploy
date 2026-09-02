# USIS CM Time — per-tab mimic plans

**Date:** 2026-09-01  
**Parent brief:** `../timekeeping_web_busybusy_cursor.md`  
**Website:** USIS CM (W3CRM + Bootstrap 5 + DataTables + `usis-ui.css` LAST)  
**Not:** BusyBusy brand, dark cyan chrome, React/MUI

Parent contract still wins on data model, CA OT engine, workflow `process_key = timecard`, field API, and do-not-regress.

## Tabs we add

| File | Nav | BusyBusy source |
|---|---|---|
| `time_live.md` | Time → Live | Dashboard + Employees roster |
| `time_my_time.md` | Time → My Time | My Status (both scrolls) |
| `time_cards.md` | Time → Time cards | Summary + Basic + Expanded + Entries |
| `time_event_log.md` | Time → Event log | Time Cards → Event Logs |
| `time_exceptions.md` | Time → Exceptions | Dashboard injury / inaccurate / break tiles |
| `time_payroll.md` | Time → Payroll period | Payroll |
| `time_map.md` | Time → Map | Map |
| `time_settings.md` | Time → Settings | Policy + cost-code library (no tracker tab) |
| `time_project_field.md` | Field → Time | Project-scoped slice of Live + cards + geofence |

## Explicitly not filed (do not build)

Cost Codes live tracker, Projects clone, Photos clone, Documents, HR Employees, Budgets, construction Schedule, Crew schedule, Weekly Attendance, Time Off, Management Lists, reports, equipment/Safety Bundle upsells.
