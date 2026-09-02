# Time → Settings — mimic plan

**Route:** `/time/settings`  
**Source:** No dedicated BusyBusy Settings screenshot. Derived from Payroll scan, Time Card Expanded toggles, Dashboard policy behavior, and parent policy JSON.  
**Parent:** `timekeeping_web_busybusy_cursor.md` §4.8, §4.6

## Job

Company policy for the clock. Amendable data, not hardcoded. Project may override geofence mode only.

## What we took from the shots (without copying their Settings rail)

- Week is Mon–Sun on Time Cards / Payroll (USIS seed is **Sunday** start — company setting, not BusyBusy’s Monday).
- Signatures required before a serious export (scan items).
- Break compliance is a first-class rule (Break Issues tile + Break Comp column).
- Hours display HH:MM on their grids; we standardize decimal to 2 places on grids, clock times on punches.
- Cost codes exist as punch metadata (“10 Specialties”) but we **do not** give them a Live tracker tab. Library lives here.

## Mimic (intent)

One settings page, sections:

1. **Workweek & timezone** — `America/Los_Angeles`, week start.
2. **Overtime** — daily 8 / daily DT 12 / weekly 40 / 7th day on.
3. **Meal & rest** — meal after 5h for 30 min; second after 10h; rest 10 min / 4h. Flags only, no auto premium pay.
4. **Punch rules** — require cost code **false**; require daily sign-off **true**; web punch **true**; open-punch flag after 12h; geofence default `flag`.
5. **Export rules** — require supervisor approve; block export with open flags.
6. **Cost code library** — add/edit/deactivate labor buckets. Seed finish-trade list. Not material SKUs. Not a who’s-working board.
7. **GPS** — breadcrumb min interval 180s; track off clock **false**.

JSON blob on company settings as in the parent brief.

## Do not copy

- BusyBusy’s per-page right SETTINGS dropdown that only switches Summary/Basic/Entries.
- A 20-row filter form as “settings.”
- Facial / kiosk / equipment toggles.
- Making cost code required after we locked it optional.

## Acceptance

- Changing `week_start` does not rewrite in-flight periods (frozen policy version on the period).
- `require_cost_code = false` allows clock-in with project only.
- Turning `web_punch_allowed` off hides buttons on My Time.
