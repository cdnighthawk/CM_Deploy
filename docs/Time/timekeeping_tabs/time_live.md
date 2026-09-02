# Time → Live — mimic plan

**Route:** `/time/live`  
**Default Time landing page**  
**Sources:** BusyBusy Dashboard (KPI + charts + exception tiles) and BusyBusy Employees (who’s-working grid)  
**Parent:** `timekeeping_web_busybusy_cursor.md` §1.1, §4.1

## Job

Office answer in one glance: who is on the clock, where, for how long, and what is broken this period.

Not a time clock homepage. No giant Clock In.

## What the screens actually do

**Dashboard**

- Three cyan hero counts: Clocked In / On Break / Clocked Out, each with a `>` drill.
- Period charts: total hours (bars by week bucket), total labor $, OT hours, OT $.
- Lower exception tiles: Injuries 7d, Inaccurate Time unresolved 7d, Break Issues unresolved 7d.
- Promo cards we will never ship (Safety Bundle, Enable Equipment, Daily Sign-In, empty photo/budget widgets).

**Employees** (this is the real operating table)

- Sub-tabs: Clocked In (4) / Clocked Out (22) / On Break (0) / Show All (26).
- Row: name, Clock In or Clock Out button, `+` overflow, GPS glyph, running Timer, Today, Week, Breaks, Last Project, Day Start, Clocked Out.
- Blue dot = on the clock. Grey dot = out.
- “Updated just now” + refresh.
- Right filter rail: employee, group, position, project, cost code.

Concrete rows from the shot: Alan Mendoza Clock Out, GPS on, timer 8:33, today 8:33, week 8:33, break 0:45, last project University of California Merced, day start 5:28 AM. Christian Childers week 16:42, day start 6:08 AM.

## Mimic (intent)

- KPI strip that drills into the table or Exceptions.
- One DataTables roster that *is* the BusyBusy Employees grid, living here — not a second HR app.
- 30s poll while the tab is visible. Relative “Updated Xs ago.”
- Supervisor actions on the row: clock out, switch project, open card, open map pin.
- Status chips via `USISUi.statusChip`: In / Break / Out.
- First punch of day (`Day Start`) as a column. Do **not** label it Late (no crew schedule yet).

## Do not copy

- Electric cyan hero blocks and mint chart banners. Primary `#1F4E5F`, canvas `#F4F6F8`.
- Clocked Out as a required hero if headcount is large — optional “Eligible not working” instead.
- Manage button that opens employee admin.
- Cost-code / employee-group / position filter clutter. Filters: employee, project, status. Persist like leads AutoFilter.
- Showing every off-clock employee as the default. Default tab = **Clocked in**. “Show all” is a second tab.
- Dollars on this page for non-payroll roles.
- Upsell / empty Photos / Budgets / Equipment cards.

## USIS layout

```
[ In n ] [ Break n ] [ Open >Nh ] [ Flags today ] [ Unsigned 7d ]

[ Hours this period ]  [ OT hours this period ]
[ Inaccurate 7d ]      [ Meal/rest 7d ]     [ Injuries 7d ]

Tabs: Clocked in | On break | Show all

DataTable
Employee | Status | Project | Since | Elapsed | Today | Week | Break | Day start | GPS | Flag | Actions
```

Labor $ / OT $ charts only if the viewer is payroll/admin and rates exist.

## Actions (row)

- View card → Time cards day drawer.
- Map → `/time/map` focused on that user.
- Clock out / Clock in (supervisor). `source = web` or `office_edit`, reason if creating a punch for someone else.
- Switch project (supervisor). Closes current `TimeEntry`, opens another, ≤1s gap.

## Acceptance

- Phone clock-in appears on Live within one poll.
- Off-clock people are hidden on the default tab.
- Off-clock people never appear on Map from this page.
- No cyan regression. No new React page.
