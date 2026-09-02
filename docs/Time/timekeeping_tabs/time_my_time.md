# Time → My Time — mimic plan

**Route:** `/time/me`  
**Sources:** BusyBusy My Status (header + hours tiles + sign banner) and the scrolled lower half (OT charts, photos, schedule empty, Most Active Projects)  
**Parent:** `timekeeping_web_busybusy_cursor.md` §1.2, §4.9

## Job

The individual surface: am I in or out, what did I work, and do I need to sign.

Journeyman who opens the website lands here. Supervisors still land on Live.

## What the screens actually do

**Upper half**

- Avatar + “Charles Dossett.”
- Buttons: Time Card, Manage.
- Blue banner: “Time Card Ready to Sign” for period ending Sunday, Aug 30 + Review & Sign.
- Hours tile: Today / This Week / Pay Period / All Time (10,017:24 hrs).
- Cost tile: same rows, All Time $561,816.29.
- Month charts: hours bars, cost area, OT hours, OT cost.
- Right rail: current job blurb (Turner / UC Merced / “10 Specialties Specialties”), View Today’s Entries, View Time Entries, Photos, Schedule, Activity Reports, Time Off, Request Time Off, Position Admin, email, phone.

**Lower half**

- OT hours / OT $ this month.
- Photos & Notes this month = 0. Recent Photos = No Thumbnails.
- Schedule = “No Work Scheduled.”
- Most Active Projects past 14 days: Office 40:00, Turner 12:00, AMG 8:00.

This particular shot is 0:00 today, so BusyBusy hid clock controls.

## Mimic (intent)

- Large In / Break / Out chip + last project name.
- Sign-ready banner when the period or a day needs `employee_sign`, or `edited_after_sign` forces a re-sign. CTA = Review & Sign (signature PNG + attest checkbox + injury question).
- Hours tiles: **Today / This week / Pay period** only. Each drills to the week grid.
- Today punch timeline (in / break / switch / out).
- Hours by project, last 14 days or current period, cap 8 rows. Use USIS project number + name.
- Web punch on this page if `web_punch_allowed`: In / Out / Break / Switch. `source = web`, IP, optional browser GPS.
- Week grid + sign day.

## Do not copy

- All Time hours or dollars (vanity + rate leak).
- Cost tiles for crew. Seed `show_own_cost_on_my_time = false`. Never on the phone.
- Manage as employee admin.
- Time Off / Request Time Off.
- Photos, Schedule, Activity Reports rail items. Construction schedule is Field → Schedule; crew schedule does not exist yet. Do not link “No Work Scheduled” to Field → Schedule.
- Empty thumbnail / “0 photos” cards.
- “10 Specialties Specialties” / “No Description” job copy. Real Project name.
- View System Data.
- Mint full-width month charts as a v1 requirement. Shared chart helper only if Live already has it.

## USIS layout

```
[Name]  [In | Break | Out]  [Time card]  [Clock In/Out/Break/Switch]

[ Sign-ready banner → Review & Sign ]

[ Hours: Today | Week | Period ]

[ Today punch timeline ]

[ Hours by project · 14d ]

[ Week grid + Sign day ]
```

Mobile: banner + status + punch buttons first.

## Acceptance

- Worker sees only self.
- Office edit after sign brings the banner back.
- Web punch writes `source = web` and does not invent GPS.
- No dollar figures for journeyman / apprentice.
