# Labor clock in / out

Status: complete
Sage CM module: Time and Expenses
Official help: https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/ClockInOut/ClockInOutOverview.htm

## Purpose

Clock in/out captures actual start, break, and end times for an employee (or a field crew, via the crew leader) against a project and approved prime contract. Entries are not job-costed until they are converted to pending labor (and optionally equipment) timecards. Geofencing can flag punches outside the project perimeter.

## Where it lives

- Browser: stopwatch icon on the Sage CM top menu → Timecard Clock In/Clock Out dialog (My Time by default).
- Project Home / Time & Expenses → Clock In / Out Stats → Convert Pending Clock-In Data; admins can clock employees out from here.
- Equipment module → Pending Equipment Clock-Ins (equipment conversion path).
- Mobile: stopwatch on the mobile app home page (GPS more accurate than browser IP geofence).
- TeamLink: not used for clock in/out.

## Who uses it

- Any security role can clock themselves in/out when the feature is enabled.
- Crew leaders: clock the crew when “Clock In/Out for Field Crews” is on.
- Users convert their own entries; crew leaders convert their crew; Administrators convert anyone.
- Financial admins later approve the resulting pending timecards.

## Prerequisites

- Feature Settings → Time & Expenses: Do you wish to use Clock In / Out for Timecards? (off by default).
- Optional: Track Breaks?; Use Geofencing? (units + distance); Clock In/Out for Field Crews?; field crews defined.
- Approved prime contract with Status Date.
- Browser location tracking enabled to persist comments.
- Project address used as geofence center.

## What the user fills out

### Clock In dialog (employee — My Time)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| My Time vs crew | Yes | Option | My Time default |
| Project | Yes | Lookup | Required at clock-in |
| Prime Contract | Yes | Lookup | Approved contract |
| Job Cost Code | No | Lookup | Optional at punch; required later at conversion if not set |
| Comments | No | Text | Saved only if location tracking is on |
| Clock In | Yes | Action | Creates the open entry |

### Breaks (if Track Breaks? is on)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Start Break | Yes to break | Action | Stopwatch → Start Break → OK |
| Stop Break | Yes to resume | Action | Stopwatch → Stop Break → OK |

### Clock Out

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Clock Out | Yes | Action | Closes the entry; net hours = work minus breaks |
| Comments | No | Text | Same location-tracking rule |

### Convert Pending Clock-In Data (labor)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Create Labor Time Entries | Yes (one or both) | Checkbox | With Create Equipment Time Entries |
| Employee selection | Yes | Multi-select | Net Hours copied into Hours |
| Change Order number | No | Lookup | Applied to converted cards |
| Work Order number | No | Lookup | Work directive |
| Payroll Item | Yes | Lookup | Per selected employee/entry |
| Job Cost Code | Yes | Lookup | Per entry |
| Billable Status | Yes | Enum | Cost Plus only for invoice import |
| Workers Comp. Code | No | Lookup | Optional |
| Timecard Comments | No | Text | Optional |
| Show (unnamed filter) | No | Checkbox | Help text truncated; can hide a column — not confirmed in help beyond “Show … checkbox” |

### Convert (equipment path)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Create Equipment Time Entries | Conditional | Checkbox | From Equipment module or combined wizard |
| Equipment + RT/IT/DT mapping | Yes if creating | Mixed | Official convert page continues after labor steps; exact equipment convert grid fields beyond “Create Equipment Time Entries” were not fully listed in the fetched help — do not invent. Conversion produces pending equipment timecards using the same RT/IT/DT model as manual equipment cards. |

### Admin clock-out others

Administrators can clock out employees who left an entry open (Clock out employees function on the overview). Extra fields on that form were not confirmed in help.

## What Sage CM saves

- Header record: clock-in/out entry (employee or crew member, project, prime, optional JCC, start/end, net hours).
- Line / child records: break intervals (start/stop) when Track Breaks? is on; location pin per punch; conversion writes pending labor timecards and/or equipment timecards.
- System-generated values: timestamps; net hours; red asterisk if outside geofence; browser IP location (web) vs GPS (mobile).
- Files / attachments: none required. USIS adds optional clock-in/out photos — Sage help does not mention photos on this form.
- Audit / workflow fields: who converted; resulting timecards start Pending.

## Statuses and lifecycle

Open (clocked in) → optional On break → Clocked out (pending conversion) → Converted to Pending labor/equipment timecard → Approved on the timecard tools. Users can clock in/out outside the geofence; those punches stay valid but flagged.

## Dates that drive alerts

No due date. Punch timestamps and geofence flags are operational. After conversion, timecard Date and T&E approval alerts apply.

## Relationships

- Upstream: Feature Settings T&E, project address, approved prime, optional field crew + equipment on crew.
- Downstream: labor timecards, equipment timecards, Labor/Equipment Hours Overview, project analytics (only after approval).

## Reports and exports

Clock-in list/stats on Time & Expenses; location pin viewer. After conversion, use labor/equipment timecard logs and exports. No separate “clock-in log report” name confirmed in help.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Clock in | `time_entries` + `time_punches` kind=`clock_in`; `POST /api/v1/time-clock/clock-in` | implemented |
| Clock out | `POST /api/v1/time-clock/clock-out` | implemented |
| Break start/end | kinds `break_start` / `break_end`; matching POST routes | implemented |
| Switch project/code mid-shift | `POST /api/v1/time-clock/switch` | implemented (Sage help did not document a “switch” action) |
| Geofence | `geofence_ok`, `geofence_distance_m`, `lat`/`lon` on punch | implemented |
| Optional punch photo | `clock_in_photo_id` / `clock_out_photo_id` / `photo_id` | implemented — Sage-only has no photo field in help |
| Convert to pending timecard | none | none |
| Crew clock-in | none | none |
| Current open shift | `GET /api/v1/time-clock/me` | implemented |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/ClockInOut/ClockInOutOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/ClockInOut/ClockInOutFunctions_Employee.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/ClockInOut/ConvertPendingEntries.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses.htm
- https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local: `backend/app/models/field_ops.py`, `backend/app/api/_field_routes.py`, `backend/app/api/_time_clock_service.py`
