# Time → Time cards — mimic plan

**Route:** `/time/cards`  
**Sources:** BusyBusy Time Cards → Summary, Basic, Expanded, Entries  
**Parent:** `timekeeping_web_busybusy_cursor.md` §4.2  
**Event Logs** is its own file (`time_event_log.md`). Do not ship five left-nav children.

## Job

The paper card for a pay period: totals, the punches that made them, attestations, and office corrections.

Period in the shots: Mon Aug 31 – Sun Sep 6. Banner total 21:19.

## What the four views actually do

**Summary** (default we copy)

- One row per employee for the period.
- Columns: Employee, Employee Group, Emp Signed, Sup Signed, Time Acc., Break Comp., Injured, Reg, OT, PTO, Total.
- Footer totals 21:19.
- Mint sparkline header across Mon–Sun (decorative — only Monday has hours in the shot).
- Rows: Aleksandr 4:45 Time Acc Yes / Break Yes; Christian 8:34 Time Acc Yes / Break **No**; Isaac 8:00 Time Acc Yes / Break Yes. Nobody signed yet.

**Basic**

- Accordion per person. Each weekday is a row with the same attestation flags + hours.
- `+` expands the day.
- Footer: Employee “Click here to sign” / Supervisor “Click here to sign.”
- Most days `---` because the period just started.

**Expanded** (the review / PDF packet)

- Punch line: Date, Start, Stop, Breaks, Activity (project + cost code), Type (Entry), Total.
- Daily Summary block repeating Time Acc / Break Comp / Injured / Reg / OT / Total.
- Signature legal text: card is complete; no hours worked off the card.
- Right toggles: Time Entries, Project Summary, Cost Code Summary, Daily Summary, Signatures.
- Time format Hours vs Decimal. Break format Total / List / Total and List.

**Entries** (the register)

- Grouped by employee with period subtotal and `+` add.
- Columns: Date, Employee, Total, Start, End, Breaks, Project, Cost Code, Type, Description.
- Aleksandr: Mon Aug 31, 4:45, 1:37 PM–6:22 PM, break 0:00, Turner / UC Merced Medical Ed, cost “10 Specialties,” Type Entry.
- Christian: 8:34, 7:02 AM–3:36 PM, Whiting-Turner / Cal Poly SLO Student Housing.
- Isaac: 8:00, 6:00 AM–2:30 PM, break 0:30, AECOM / USCG Key West. Start/end marked EDT.

## Mimic (intent) — three view toggles, one page

| Toggle | BusyBusy analog | USIS |
|---|---|---|
| **Summary** | Summary | Default DataTable, one row per employee |
| **Card** | Expanded (+ Basic’s day list) | Click row or this toggle: punches + daily totals + sign lines |
| **Entries** | Entries | Flat `TimeEntry` register, groupable by employee |

Skip a fourth “Basic” page. Card view covers it.

Period pager: previous / next `TimecardPeriod` (company week, seed Sunday). Not a mint sparkline as a required widget.

## Summary columns (USIS)

`Employee | Emp signed | Super approved | Flags | Reg | OT | DT | Premium | Total`

- Hide PTO unless a PTO table already exists.
- Hide Employee Group.
- Flags = chips (meal, unsigned, GPS, edited-after-sign), not three Yes/No mystery columns. Map Time Acc → `missing_signoff` / attest; Break Comp → `missing_meal` / `missing_rest`; Injured → `TimecardDay.injury_reported`.
- Click row → Card + day drawer.

## Card / day drawer

- Punch timeline with project, optional cost code, GPS chip, source.
- Server-computed Reg / OT / DT / meal minutes.
- Add / Edit / Split / Delete. Office writes `source = office_edit`, `entered_by`, **reason required**.
- Split at a timestamp, gap ≤ 1s (forgotten cost-code / job switch).
- Employee sign + supervisor approve (workflow `timecard`).
- Attestation copy in Flask PDF, not only in the UI:
  - Employee: hours are complete and accurate; nothing worked off the card; injury yes/no.
- Linked photo if one exists — do not embed a gallery.
- Audit snippet → full Event log filtered to this user/day.

## Entries view columns

`Date | Employee | Start | End | Break | Total | Project | Cost code | Source | Flags | Actions`

Use USIS project number + name, not GC-only strings. Cost code column hidden if blank. Source = mobile / web / office_edit.

`+` add punch = same office-add form as the drawer.

## Do not copy

- Five Time Cards children in the left nav.
- Mint full-width 21:19 banner as brand. A quiet period total is enough.
- Right SETTINGS rail of 8–10 filters. Employee, project, signed/flagged/locked. Persist localStorage.
- Decimal vs HH:MM as a page setting — pick **decimal hours to 2 places** on grids, show clock times as local `h:mm A` on punches. PDF can show both.
- Project Summary / Cost Code Summary toggles as v1 (no cost-code tracker).
- Type “Entry” as a user-facing field. Use `entry_type` work/break under the hood.
- Editing hours as a typed total. Always write punches; `TimecardDay` is computed.

## Locked rows

Period `locked` / `exported` = read-only. Payroll admin Reopen only.

## Acceptance

- Summary totals equal Entries sum for that user.
- Break Comp No on a 8.5h day with no meal punch raises `missing_meal`.
- Sign then office edit clears signature and sets `edited_after_sign`.
- T&M ticket hours stay on this card (billing copy elsewhere).
