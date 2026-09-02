# Time → Exceptions — mimic plan

**Route:** `/time/exceptions`  
**Source:** BusyBusy Dashboard lower tiles (Injuries, Inaccurate Time, Break Issues) — they have no standalone Exceptions page in the shots  
**Parent:** `timekeeping_web_busybusy_cursor.md` §4.3

## Job

Payroll’s morning queue. Every punch that needs a human before export.

BusyBusy scatters this as three dashboard counts. We give it a real page so “2 break issues” is clickable work, not a decoration.

## What the source tiles do

- **INJURIES · PAST 7 DAYS** — count only (0 in the shot).
- **INACCURATE TIME · UNRESOLVED · PAST 7 DAYS** — 0. Catch-all for bad cards.
- **BREAK ISSUES · UNRESOLVED · PAST 7 DAYS** — 2. Meal/rest problems.

No drill-in UI was captured. Time Card Summary’s Time Acc / Break Comp / Injured columns are the same flags in grid form (Christian Break Comp = No).

## Mimic (intent)

One queue, not three modules.

Default filter: **open**, trailing 7 days + anything still blocking the open pay period.

Columns:

`When | Employee | Project | Type | Detail | Status | Assignee`

Status: `open` / `accepted` / `corrected` / `dismissed`.

Actions:

- **Accept** — keep the punch, clear flag, reason required.
- **Correct** — jump to the day drawer.
- **Dismiss** — not a real issue, reason required.

KPI chips at top (clickable filters): Injuries · Inaccurate · Meal/rest · GPS/offsite · Unsigned · Open punch. Counts match Live.

## Flag types (seed)

| `flag_type` | BusyBusy analog |
|---|---|
| `missing_meal` / `missing_rest` | Break Issues |
| `missing_signoff` / `edited_after_sign` / `overlap` / `clock_skew` / `cost_code_missing` | Inaccurate Time |
| `injury_reported` | Injuries (from sign-off, plus Daily Report incident if that table exists) |
| `offsite` / `gps_denied` / `blocked_override` | GPS — not on those three tiles but required |
| `open_punch` | Still in past shift-end rule |

Do not invent a separate EHS product from the Injuries chip.

## Do not copy

- Violet accent bars and 7-day-only thinking. Open flags on the current period stay visible even if older than 7 days.
- A tile with no click-through.
- Auto-paying a meal premium. Flag only; payroll decides.

## Optional AI

Purple “Review flags with Local AI” (`time_exception_review`) only if it is less than half a day. Human still Accepts/Corrects. Grok untouched. Skip rather than block v1.

## Acceptance

- 8h+ day with no unpaid break ≥ 30 min after 5 hours → `missing_meal` row.
- Accept writes reason and drops the count on Live.
- Export blocked while `block_export_with_open_flags` and any `open` flag remain.
