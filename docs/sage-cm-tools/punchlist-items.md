# Punchlist items

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/Punchlist/PunchlistOverview.htm

## Purpose

Punchlist items capture **project-specific** non-conforming work from owner/architect/GC walkthroughs near the end of the job. Contracts often require all punch items closed before the final invoice. Unlike checklists, punch items are not reused as company templates (Excel import exists for a project). Field staff close items from the mobile app.

## Where it lives

- **Project Home** → Quality Control → **Punchlist Items**.
- Add: inspection date/inspectors (optional) → item grid (location, description, photo, responsible, due).
- **Quality Control Calendar:** inspection date and item due date.
- **Team Open Items:** Open + responsible match + Completion Date null.
- **Mobile:** Punchlist items R, E, A, D; **Email option: Yes**.
- **TeamLink:** open items included in the external-team email (overview).

## Who uses it

- GC/CM, architect, and owner identify items on a walk.
- **Responsible** company/contact (usually the firm fixing the work) — required in directory; contact recommended for email.
- **Inspectors** (directory company/contact) on the inspection date.
- Superintendents update/close from mobile.

## Prerequisites

- Project; inspectors and responsible companies in the **project directory** (your firm, subs, suppliers, architect, owner).
- Optional existing inspection date to reuse (Option B).

## What the user fills out

### Step 1 — Inspection date and inspectors (Skip or Option A allowed)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Option A — Do Not Enter Inspection Date | — | Choice | Skip inspectors |
| Option B — Select an Existing Inspection Date and Inspectors | — | Date picker | Reuse a prior walk |
| Option C — Enter New Inspection Date and Inspectors | — | New walk | |
| Inspection Date | If B or C | Date | QC Calendar (punchlist inspection) |
| Inspector Company | If C | Directory company | One or more inspectors |
| Inspector Contact | If C | Directory contact | |

### Step 2 — Punchlist items

**Defaults** (applied after description is entered):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Default Location | Help: select | Text | Shared location for the batch |
| Default Responsible Company | No | Directory | Usually the fixer |
| Default Responsible Contact | No | Directory | Recommended for emailing open items |
| Default Due Date | No | Date | |

**Each item:**

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Punchlist Item # | Yes (auto) | Number/text | Auto-generated; user may update |
| Description | Yes | Text | Defect / non-conforming work |
| File (image) | No | Upload | Choose file — illustrates the issue |
| Responsible Company | No | Directory | Overrides default |
| Responsible Contact | No | Directory | Overrides default |
| Due Date | No | Date | Calendar + alerts |
| Location | Bulk / default | Text | Bulk action can update location |

Add Extra Rows for more items at the same location; Add & New for another location; Add & Finish to complete.

### Edit / close (overview)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Status | Yes to close | Status | Set to **Closed** |
| Completion Date | Yes to close | Date | Required when closing; null = still open for email |

### Bulk actions

- Update responsible company and contact
- Update inspection date
- Update location
- Update due date
- Update completion date
- Delete selected items

### Import

- Import punchlist items from an Excel file (overview). Column mapping **not confirmed in help**.

## What Sage CM saves

- **Header / grouping:** Inspection date + inspector company/contacts (optional). Items can share a location/defaults.
- **Line / child records:** Each punchlist item (number, description, location, responsible, due, completion, status, optional image).
- **System-generated values:** Punchlist Item #.
- **Files / attachments:** Per-item image on add; also Linked files on the record (feature list includes Punchlist Items).
- **Audit / workflow fields:** Status Open/Closed; Completion Date; inspection date; Team Open Items + calendar.

## Statuses and lifecycle

| Status | Effect |
|---|---|
| Open | Calendar (due date); Team Open Items if Completion Date null and Responsible matches |
| Closed | Set Status Closed **and** enter Completion Date |

Recommended close path: mobile real-time; fallback: print open-item log, mark in field, update in office.

## Dates that drive alerts

| Feature | Date |
|---|---|
| Punchlist inspection | Inspection date |
| Punchlist item | Due date |

Completion Date closes open items; it is not the alerts-table date.

## Relationships

- **Upstream:** Project directory; optional drawings/photos; Excel import.
- **Downstream:** Final invoice gate (contractual, not an automatic Sage lock documented here); Team Open Items; mobile email.
- **Not** a checklist template.

## Reports and exports

- Punchlist items **log report** of open items (print for field).
- Download punchlist item reports (overview).
- Excel import inbound.

## USIS / CM_Deploy mapping

`Issue` is a unified tracker whose docstring mentions punch, but there is no Sage punchlist module (no inspection date, responsible directory company, or Open/Closed + Completion Date).

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Punchlist item | `tracker_issues` (`source_type` can include punch per model comment) | stub |
| Title / description / due / assignee | `title`, `description`, `due_date`, `assignee_id` | partial |
| Status / resolved | `status`, `resolved_at` | partial |
| Inspection date / inspectors | none | none |
| Responsible company (directory) | none | none |
| Completion Date / Closed | none (use `resolved_at`) | stub |
| Issues UI | `construction/issues.html` | partial (generic issues) |
| Drawing pin | `drawing_id`, `sheet_number` | implemented (Sage add form uses optional image, not drawing pin) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Punchlist/PunchlistOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Punchlist/PunchlistAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `backend/app/models/issue.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/issues.html`
