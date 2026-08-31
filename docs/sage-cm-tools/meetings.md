# Meetings

Status: complete
Sage CM module: Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Documentation/MeetingMinutes/MeetingMinutesOverview.htm

## Purpose

Meetings (meeting minutes) records owner, coordination, and subcontractor meetings: header (when/where/why), attendees, rolling discussion items (new and old business), and linked files. Open items stay on the Documentation Calendar and Team Open Items until closed. Meeting numbers are coordinated with Safety Meetings.

## Where it lives

- **Project Home** → Documentation → **Meetings**.
- List of meetings → meeting detail (New Business Items, imported old items, attendees, files).
- **Documentation Overview** → Documentation Calendar; Team Open Items (open meeting items).
- **Mobile:** Meetings are **not** listed on the iOS feature matrix.
- **TeamLink:** internal employees cannot use the portal; open items email can send a hyperlink + security code for follow-up.

## Who uses it

- Facilitator and note taker (usually the GC firm) create the meeting and minutes.
- PMs add discussion items and assign responsible company/contact + due date.
- Attendees are imported from the project directory or a prior meeting.
- External companies receive invitations and HTML minutes; they close items by responding through assigned responsibility, not by authoring the meeting (portal lock rules apply to locked documentation records).

## Prerequisites

- Project; **Prime Contract** (required on add).
- All attendee companies/contacts in the **project directory**.
- Settings → Feature Settings → Documentation → **Meeting Type** (group/sort).
- Prior meetings if importing attendees or old business items.

## What the user fills out

### Header (Actions → Add Manually, step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project number | No | Project picker | Defaults from current project |
| Prime Contract | Yes | Prime contract | |
| Meeting # | No | Text/number | Auto next number/format; user may override |
| Date | No | Date | Defaults to today |
| Meeting Type | Yes | Dropdown | Feature Settings → Documentation |
| Start Time | No | Time | |
| Finish Time | No | Time | |
| Location | No | Text | |
| Subject | Yes | Text | |
| Meeting Purpose | No | Text | |
| Facilitator Company | No | Directory company | Usually your firm |
| Facilitator Contact | No | Directory contact | |
| Note Taker Company | No | Directory company | Usually your firm |
| Note Taker Contact | No | Directory contact | |
| Set Next Meeting Date as well? | No | Checkbox | If set, enter next Date, Start Time, Finish Time, Location |

### Attendees (step 2)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Import Method | Yes if adding | Dropdown | Import Project Directory Contacts **or** Import Prior Meeting Attendees |
| Search | No | Text | Filter list |
| Company contacts | Yes if adding | Multi-select | One or more directory contacts |

Skip is allowed.

### Import prior meeting items (step 3)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Type | No | Filter | Prior item type |
| Meeting # | No | Filter | Source meeting |
| Status | No | Filter | Prior item status |
| Select Meeting Items | Yes if importing | Multi-select | Becomes old business on the new meeting |

Skip is allowed.

### New business discussion item (meeting detail → New Business Items → Add)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Item # | No | Text/number | User may update |
| Subject | Yes | Text | |
| Discussion | Yes | Text | Description |
| Category | No | Text or lookup | e.g. Concrete, Electrical, Plumbing, Permits; magnifying glass for existing |
| Responsible Company | No | Directory company | Open-item email uses this |
| Responsible Contact | No | Directory contact | |
| Due Date | No | Date | Documentation Calendar + Alerts while open |
| Closed | No | Checkbox | Status and Conclusion Comments section |
| Conclusion comments | No | Text | Entered when closing |

### Linked files (step 4)

Same pattern as other documentation: local upload (48 files / 500 MB) or Link Existing Files (Drawings & Specs, Photos, All Other Records), same project/lead only.

## What Sage CM saves

- **Header record:** Meeting (number, date, type, times, location, subject, purpose, prime contract, facilitator, note taker, optional next-meeting fields).
- **Line / child records:** Attendees (company/contact). New business items. Old business items imported from prior meetings (same item fields; alerts treat both new and old due dates).
- **System-generated values:** Meeting # sequence (shared coordination with Safety Meetings — safety meeting # “is coordinated with all meetings created in the Documentation module”).
- **Files / attachments:** Linked files on the meeting.
- **Audit / workflow fields:** Item status Open vs Closed; conclusion comments; open-item email when status Open and responsible = selected company/contact.

## Statuses and lifecycle

1. Add meeting → optionally attendees → optionally import old items → files.
2. Email meeting invitation to attendees.
3. Add new discussion items (Open by default).
4. Items stay on calendar/alerts while Open and due date set.
5. Close item: Closed checkbox + conclusion comments.
6. Print/share minutes; email minutes in HTML.
7. Next meeting can import prior attendees and still-open (or selected) items.

Meeting item open-item rule: **Mtg Item Status = Open** and Company Responsible matches the emailed company/contact.

## Dates that drive alerts

| Feature | Date |
|---|---|
| Meetings | Meeting date |
| Meetings new business item | Item due date |
| Meetings old business item | Item due date |

## Relationships

- **Upstream:** Project, prime contract, project directory, prior meetings, photos/drawings.
- **Downstream:** Next meeting import; Team Open Items email; Documentation Calendar.
- **Sibling:** Safety Meetings use a related meeting-number sequence but live under QC/Safety and use Safety Topic instead of Meeting Type/Subject.

## Reports and exports

- Print or share meeting minutes.
- Email minutes in HTML format.
- Email invitation to attendees.
- Documentation Calendar / Home Alerts.

## USIS / CM_Deploy mapping

No Sage-style meeting minutes model. W3CRM `mom.html` / `mom-detail.html` are generic construction MOM pages, not wired to a meeting-items API.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Meeting header | none (`construction/mom.html` UI only) | none |
| Attendees | none | none |
| Discussion items / due dates | none | none |
| Safety toolbox / pretask attendees | `daily_pretasks.attendees`; safety-automation TOOLBOX | none (different tool) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/MeetingMinutes/MeetingMinutesOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/MeetingMinutes/MeetingMinutesAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/MeetingMinutes/MeetingMinutesAddNewBusiness.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/SafetyMeetings/SafetyMeetingAddManually.htm (numbering coordination)
- Local files reviewed
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/mom.html`
  - `backend/app/models/safety.py`
