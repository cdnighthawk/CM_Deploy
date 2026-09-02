# Time → Event log — mimic plan

**Route:** `/time/events`  
**Also:** filtered from a Time card day drawer  
**Source:** BusyBusy Time Cards → Event Logs  
**Parent:** `TimePunchEvent` + existing audit log in `timekeeping_web_busybusy_cursor.md`

## Job

Defensible trail of every tap and every office change. This is not hours. It is *who did what to the clock*.

## What the screen actually does

Period header Mon Aug 31 – Sun Sep 6 (the log in the shot is mostly **Tue Sep 1** actions touching **Aug 24–29** punches).

Columns:

`Action | Performed | Employee | Details | Performed By | GPS | Device`

Actions in the shot:

- **Edit** — Laura Dossett-Mora changed Charles Dossett’s Wednesday Office 6:00 AM–2:30 PM (cost “00 Construction Management Project Management”) from Web Browser. No GPS.
- **Manual** — Laura created punches on Charles’s card (Turner 2:30–7:00 PM, Office 7:00 AM–3:30 PM, etc.) from Web Browser.
- **Break Start / Break End** — crew self-taps. GPS pin present. Devices: iPhone 16 Pro Max, SM-S928U1, iPhone18,1.

Details cell stacks date, time range, project, cost code.

Right filters: Action, Employee, Group, Position, Performed By, Project, Cost Code.

## Mimic (intent)

- Append-only list. Never edit a log row. Void + new event if a punch changes.
- Same columns, renamed clearly:

`When recorded | Action | Whose card | Interval + project | By | Source | GPS | Device`

- Action vocabulary to store (not BusyBusy labels only):

`clock_in | clock_out | break_start | break_end | switch | manual_add | edit | split | delete_void | sign | unsign | approve | lock`

- Source: `mobile` / `supervisor_mobile` / `web` / `office_edit`.
- GPS column = pin if lat/lon present, else blank. Click pin → Map at that point.
- Device string as sent by the phone (`iPhone`, `SM-…`) or `Web` + IP for office.
- Office Edit/Manual **must** include `performed_by` and reason (in details or a Reason column).

## Do not copy

- A fifth Time Cards child in the sidebar is optional; a top-level Time → Event log is cleaner.
- Empty GPS cells styled as failures. Blank means web/office.
- Group / Position / Cost Code Group filters.
- Treating this as a place to fix hours. Row click opens the card. Corrections happen on the card.

## Implementation

- Primary write path is `TimePunchEvent`.
- Also write the existing company audit log (`before` / `after` JSON) on office edits.
- Filters: date range, employee, action, performed-by, project, source. DataTables + persist.

## Acceptance

- Phone break start produces a row with GPS + device and `performed_by = employee`.
- Office manual punch produces a row with `source = office_edit`, no GPS, reason required.
- Deleting/voiding a punch adds a `delete_void` row; the original event remains.
