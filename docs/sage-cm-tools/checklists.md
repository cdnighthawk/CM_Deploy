# Checklists

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/Checklist/ChecklistOverview.htm

## Purpose

Checklists are reusable **internal QC process** lists (footings, framing, electrical rough-in, etc.) — not punchlist defects. Templates live in Settings; project/lead runs copy the template so crews check items with a per-item responsible company, contact, and due date. External TeamLink users cannot see checklists.

## Where it lives

- **Lead or Project Home** → Quality Control / QC and Safety → **Checklists**.
- Settings → **Templates & Reports → Checklist Templates** (company-wide).
- Checklist detail: name, prime contract, sections, items, linked files.
- **Mobile:** Checklists R, E, A, D.
- **TeamLink:** **Cannot** view checklists or checklist items.

## Who uses it

- Admins author templates once.
- Superintendents/PMs add a checklist from a template or manually on a lead/project.
- Responsible company/contact (directory) owns each **item**, not the whole list.
- Bulk actions used by office staff to reassign, date-stamp, or delete many items.

## Prerequisites

- Lead or project; responsible review company in the **project directory**.
- Optional prime contract (projects).
- Optional template in Settings → Templates & Reports → Checklist Templates.
- Optional sections if the list is long.

## What the user fills out

### Header (Actions → Add Manually, step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead or Project number | No | Picker | Defaults from context |
| Prime Contract number | No | Prime contract | Projects only |
| Checklist Name | Yes | Text | Also used as Home Alerts Subject |

Edit later: checklist name or prime contract reference. Copy checklist to another lead or project is a separate function.

### Sections (step 2, optional — Skip allowed)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Section Code | Yes if adding sections | Text | e.g. 01, 02, … 10; A, B, C; A.01, B.01 |
| Section Name | Yes if adding sections | Text | |

### Checklist items (step 3 or later Add checklist items)

**Default Information For Checklist Items** (applied to each new row, overridable):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Responsible Company | No | Directory company | Per item, not header |
| Responsible Contact | No | Directory contact | Per item |
| Default Due Date | No | Date | Per item |

**Each item:**

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Section | No | Section picker | If sections exist |
| Order number | No | Number | User may update; bulk can reset by section + existing order |
| Description | Yes | Text | |
| Responsible Company | No | Directory | Overrides default |
| Responsible Contact | No | Directory | Overrides default |
| Due Date | No | Date | Alerts; Home Alerts uses earliest item due date |
| Checked date | No | Date | Bulk update; “checklist inspection” alert uses **Review date** (help name) |

### Bulk actions (Choose Bulk Action)

- Update the section
- Update the checked date
- Update the due date
- Update the responsible company and contact
- Reset the order number based on section and existing order number
- Delete the selected items

### Linked files (step 4)

Standard QC file step: 48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records.

## What Sage CM saves

- **Header record:** Checklist (name, lead/project, optional prime contract).
- **Line / child records:** Sections (code + name). Items (order, section, description, responsible company/contact, due date, checked/review date).
- **System-generated values:** Order numbers; template copy onto project/lead.
- **Files / attachments:** Linked files on the checklist record.
- **Audit / workflow fields:** Per-item responsibility; not on Team Open Items; TeamLink hidden.

## Statuses and lifecycle

No overall Open/Closed name in help. Item progress is **due date** vs **checked date** (review date on alerts).

1. Create template (optional) or add manually.
2. Add sections, then items.
3. Field/office check items (checked date); bulk update.
4. Copy to another lead/project; download checklist.

Home Alerts: **one** notification per checklist; Date = earliest item due date; Subject = checklist name.

## Dates that drive alerts

| Feature | Date |
|---|---|
| Checklist inspection | Review date |
| Checklist item | Due date |

## Relationships

- **Upstream:** Checklist Templates; project directory; prime contract; Feature Settings (indirect).
- **Downstream:** QC Calendar; Home Alerts; download; copy to another project. **Not** Team Open Items. **Not** punchlist.
- **USIS playbooks** are operational runs (open/complete/cancelled), not Sage QC phase checklists.

## Reports and exports

- Download a checklist.
- Copy a checklist to another lead or project.
- Related reading cited by Sage: Production Checklist for Builders and Superintendents (Kuchinsky/Haasl) — external book, not a Sage report.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| QC checklist header | none | none |
| Template in Settings | `checklist_templates` (company playbook, Plan 22) | partial (different purpose) |
| Template steps | `checklist_template_steps` (sequence, title, body, default assignee user) | partial |
| Project run | `checklist_runs` (`open` / `complete` / `cancelled`, `is_blocked`) | partial |
| Run steps | `checklist_run_steps` (`pending` / `done` / `skipped`) | partial |
| Per-item directory company/due/checked | none | none |
| Daily pretask checklist keys | `daily_pretasks.checklist` JSON | none (safety PTP, not QC) |
| Submittal checklist | `submittal_checklist_items` | none (correspondence) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Checklist/ChecklistOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Checklist/ChecklistAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/Checklist/ChecklistItemsAdd.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/playbook.py`
  - `backend/app/models/safety.py`
  - `backend/app/models/submittal.py`
