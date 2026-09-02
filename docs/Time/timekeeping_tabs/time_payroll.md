# Time → Payroll period — mimic plan

**Route:** `/time/payroll`  
**Source:** BusyBusy Payroll  
**Parent:** `timekeeping_web_busybusy_cursor.md` §4.4

## Job

Close the week and hand a file to QuickBooks / ADP / Paychex. Not tax, not checks, not BusyPayroll.

## What the screen actually does

Period: **Mon, Aug 24 – Sun, Aug 30**. Prev/next chevrons.

**Green Hours tile**

| Bucket | Shot |
|---|---|
| Regular | 384:23 |
| Overtime | 79:55 |
| Double Time | 2:05 |
| PTO | 0:00 |
| Total | 466:23 |

**Scan Payroll** checklist (empty circles + Scan Now):

- Pay Period Complete
- All Employees Signed
- No Time Entry Conflicts
- All Time Off Requests Processed
- All Supervisors Signed
- All Time Cards Locked
- All Closed Time Entries
- All Breaks Compliant

Green **Export Payroll** top right.

**Grid**

`Employee | Employee Signed | Supervisor Signed | Rate | Reg Hrs | OT Hrs | DT Hrs | PTO Hrs | Total Hrs`

Padlock on some names = locked card.

Rates in the shot mix hourly ($63.03, $52.24, $37.82, $30.00) and salary ($75,000.00/yr). Several people at $0.00/hr. Charles 28:00 reg + 8:00 OT, unsigned. Sekou 36:23 + 2:05 DT. Nobody has supervisor signed = Yes.

Filters: employee, group, position, wage types, time-card issue.

## Mimic (intent)

- Period list, then this detail for one `TimecardPeriod`.
- Hours summary card (USIS primary, not lime green): Reg / OT / DT / Total. Hide PTO.
- **Scan** as real gates, not decoration. `Scan Now` recomputes from server.

USIS scan items:

| Check | Pass when |
|---|---|
| Period complete | `period_end` < now (or admin override) |
| All employees signed | every clock-eligible row with hours has `signed_at` |
| All supervisors approved | workflow past `supervisor_approve` |
| No conflicts | no `overlap`, `clock_skew`, open `edited_after_sign` |
| All entries closed | no open `TimeEntry` for that period |
| Breaks compliant | no open `missing_meal` / `missing_rest` |
| Flags clear | no `open` TimeFlag if `block_export_with_open_flags` |
| Cards locked | after payroll hits Lock |

Drop “All Time Off Requests Processed.”

- Table columns:

`Employee | Class | Emp signed | Super approved | Reg | OT | DT | Premium | Total | Projects | Lock`

Rate column **payroll admin only**. Do not show $0.00/hr as fake data. If no `EmployeeTimeProfile.hourly_rate`, show “—”.

- Buttons: Lock period, Unlock (payroll admin), Export CSV (Documents Hub + download), Print timecard PDF (Flask + Jinja2).
- Export blocked when scan fails and `block_export_with_open_flags` is true (seed true).
- CSV seed columns stay as parent brief. Include `cost_code` when the punch has one; blank is fine.

## Do not copy

- Lime Export button + lime hours slab as brand.
- PTO column / time-off scan item.
- Publishing rates to supers or crew.
- Tax, net pay, printed checks, ADP live connector.
- Treating $75k/yr salary as something the OT engine must solve in v1. Store classification + rate type; hourly OT math is the v1 path. Salary people still get a card of hours.

## Workflow

`capture → employee_sign → supervisor_approve → payroll_lock → exported`  
Frozen definition version on the in-flight period.

## Acceptance

- Scan lists the three unsigned people from a fixture like the shot.
- Export with open meal flags returns 409 when the setting is on.
- CSV lands in Documents Hub under the company/period, not only a browser download.
- Lock makes Time cards read-only.
