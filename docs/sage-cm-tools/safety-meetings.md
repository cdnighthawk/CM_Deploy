# Safety meetings

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/SafetyMeetings/SafetyMeetingAddManually.htm

## Purpose

Safety meetings record toolbox / site safety talks: date, facilitator, topic and details, attendees, and files. Meeting **numbers are coordinated with Documentation Meetings** (same sequence). Discussion-item **due dates** appear on the Safety Calendar / Home Alerts. This is not the Documentation Meetings feature (no Meeting Type / New Business grid on the add wizard).

## Where it lives

- **Project Home** → Safety / QC and Safety → **Safety Meetings**.
- Add wizard: general information → attendees → linked files.
- **Safety Overview → Safety Calendar** (discussion item due date).
- **Mobile:** Safety meetings R, E, A, D.
- **Team Open Items:** Safety meetings are **not** in the open-items table.

## Who uses it

- Facilitator company/contact (usually your firm).
- Attendees imported from project directory or prior **meeting** attendees (same import methods as Documentation meetings).
- Field crews sign in via imported contacts; extra discussion-item UI beyond alerts is **not fully confirmed** on the add page.

## Prerequisites

- Project; optional prime contract.
- Facilitator and attendees in the **project directory**.
- Prior meetings if importing prior attendees.

## What the user fills out

### Header (step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | |
| Prime Contract | No | Prime contract | |
| Meeting # | Yes (auto) | Text/number | Auto-generated; **coordinated with Documentation meetings** |
| Date | Yes (help: select) | Date | Defaults to today |
| Facilitator Company | No | Directory | Usually your firm |
| Facilitator Contact | No | Directory | |
| Start Time | No | Time | |
| Finish Time | No | Time | |
| Location | No | Text | |
| Safety Topic | Yes | Text | |
| Safety Topic Details | No | Text | General description of topics covered |

### Attendees (step 2, Skip allowed)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Import Method | Yes if adding | Dropdown | Import Project Directory Contacts **or** Import Prior Meeting Attendees |
| Search | No | Text | |
| Company contacts | Yes if adding | Multi-select | |

### Discussion items (alerts only)

The add wizard does **not** list a New Business grid. The official alerts table includes **Safety meeting discussion item → Due date**. Treat discussion items + due date as persisted child records confirmed by AlertsCalendar; create-form field names other than Due Date are **not confirmed in help**.

### Linked files (step 3)

48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records.

## What Sage CM saves

- **Header record:** Meeting # (shared sequence with Documentation meetings), date, times, location, facilitator, safety topic + details, prime contract.
- **Line / child records:** Attendees (company/contact). Discussion items with due date (confirmed via alerts).
- **System-generated values:** Meeting #.
- **Files / attachments:** Linked files (sign-in sheets, toolbox PDFs, photos).
- **Audit / workflow fields:** Discussion item due date on Safety Calendar.

## Statuses and lifecycle

No Open/Closed header in the add help. Lifecycle: create meeting → add attendees → attach files → (optionally) discussion items with due dates until resolved.

## Dates that drive alerts

| Feature | Date |
|---|---|
| Safety meeting discussion item | Due date |

Meeting Date is **not** on the Safety alerts table (Documentation Meetings **are** alerted by meeting date).

## Relationships

- **Upstream:** Project directory; prior meeting attendees; Documentation meeting number sequence.
- **Downstream:** Safety Calendar; linked files; mobile.
- **Sibling:** Documentation Meetings (Subject, Meeting Type, new/old business, invitation/HTML minutes).
- **USIS:** Daily pretask attendees/signatures and TOOLBOX packet are not this Sage record.

## Reports and exports

- Print/share pattern **not named** on the add page (feature exists in QC/Safety reporting generally).
- Mobile full CRUD.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Safety meeting header + topic | none | none |
| Toolbox talk packet | `docs/safety-automation/templates/forms/TOOLBOX.md` | none |
| Pretask attendees / supervisor sign | `daily_pretasks.attendees`, `supervisor_name`, `supervisor_signature` | none |
| Mobile pretask | `mobile/SAFETY.md`, `mobile/src/api/safety.ts` | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/SafetyMeetings/SafetyMeetingAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/MeetingMinutes/MeetingMinutesAddManually.htm
- Local files reviewed
  - `docs/safety-automation/templates/forms/TOOLBOX.md`
  - `backend/app/models/safety.py`
  - `mobile/SAFETY.md`
