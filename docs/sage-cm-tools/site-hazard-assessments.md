# Site hazard assessments

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/Modules/QCSafety/SiteHazardAssessment/SiteHazardAssessmentAddManually.htm

## Purpose

A site hazard assessment (SHA) is a dated inspection that imports **catalog hazard items** (Feature Settings → QC & Safety) onto a lead or project, then tracks location, priority, controls, PPE, responsible party, and estimated/actual completion. It is Sage’s JHA/hazard register — not the USIS daily pretask.

## Where it lives

- **Lead or Project Home** → Safety section → **Site Hazard Assessments**.
- Add wizard: inspection date + inspectors → import hazard items → linked files.
- Detail: Applicable Site Hazard Items (edit one or bulk).
- **Mobile:** Site hazard assessments R, E, A, D.
- **Alerts / Team Open Items:** SHA is **not** on the Safety alerts-date table and **not** on the open-items email table.

## Who uses it

- Inspectors (directory companies/contacts) on the assessment date.
- Optional **Responsible Company/Contact** per hazard (often left blank unless a firm owns the item).
- Safety/PM staff update plans to eliminate/control, PPE, and completion dates.

## Prerequisites

- Lead or project; optional prime contract on projects.
- Inspector companies in the **project directory**.
- Hazardous item catalog in **Settings → Feature Settings → QC & Safety** (required for import).

## What the user fills out

### Header (step 1)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead or Project number | No | Picker | |
| Prime Contract number | No | Prime contract | Projects only |
| Assessment # | No | Text/number | Auto-generated; user may update |
| Date | No | Date | Site inspection date; defaults to today |
| Inspectors Company / Contact | No | Multi directory | One or more; dropdown from project directory |

### Default Hazard Item Information (step 2, Skip allowed)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Default Location | No | Text | Applied to imported items |
| Default Priority | No | Dropdown | Values **not enumerated in help** |
| Default Est. Completion Date | No | Date | When hazards should be resolved/eliminated |
| Default Responsible Company | No | Directory | Typically left blank |
| Default Responsible Contact | No | Directory | Typically left blank |
| Hazardous Items | Yes if importing | Multi-select | Catalog from Feature Settings |

### Edit one hazard item (Applicable Site Hazard Items)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Hazard category | No | Catalog | |
| Category item number | No | Catalog / text | Help: Category Item # |
| Description | No | Text | |
| Location | No | Text | |
| Priority | No | Dropdown | |
| Task / Task description | No | Text | |
| Plans to eliminate or control the hazard | No | Text | |
| Required personal protective equipment | No | Text | Required Personal Protective Eqp. |
| Responsible Company | No | Directory | |
| Responsible Contact | No | Directory | |
| Estimated completion date | No | Date | |
| Actual completion date | No | Date | |
| Completion comments | No | Text | Listed on the older edit-topic wording |

### Bulk update

Checkboxes + values for: Responsible Company and Contact; Location; Priority; Estimated Completion Date; Actual Completion Date; Delete.

### Linked files (step 3)

48 files / 500 MB; Link Existing Files Photos / Drawings & Specs / All Other Records.

## What Sage CM saves

- **Header record:** Assessment #, date, inspectors, lead/project, prime contract.
- **Line / child records:** Hazard items (category, item #, description, location, priority, task, controls, PPE, responsible, est/actual completion, comments).
- **System-generated values:** Assessment #.
- **Files / attachments:** Linked files on the SHA.
- **Audit / workflow fields:** Completion dates; no official Open status in help.

## Statuses and lifecycle

No Open/Closed header status in help. Item lifecycle is estimated → actual completion (and optional comments). Catalog items are imported, then edited until eliminated/controlled.

## Dates that drive alerts

SHA dates are **not** on the Safety alerts table. Est./actual completion are operational fields only.

## Relationships

- **Upstream:** Feature Settings hazard catalog; project directory inspectors.
- **Downstream:** Linked photos; mobile SHA; Word template SiteHazardAssessment.dot (Sage reporting catalog — bookmark list **not fetched** here).
- **Not** Daily Pretask (`daily_pretasks.tasks[].hazards`) and **not** company IIPP packet.

## Reports and exports

- Print/download SHA (standard QC/Safety pattern).
- Import catalog items onto an existing assessment (`SiteHazardAssessmentItemsImport.htm`).

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| SHA header + catalog items | none | none |
| Pretask task hazards | `daily_pretasks.tasks` (`jha_complete`, `task`, `hazards`, `steps`) | none (daily PTP) |
| Project scope flags | `project_safety_profiles.payload.scope` | none (SSSP chapters, not SHA items) |
| SSSP / site card | `docs/safety-automation/templates/project/` | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/SiteHazardAssessment/SiteHazardAssessmentAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/SiteHazardAssessment/SiteHazardAssessmentItemsImport.htm
  - https://help.sagecm.intacct.com/Content/Modules/QCSafety/SiteHazardAssessment/SiteHazardAssessmentItemsEdit.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
- Local files reviewed
  - `backend/app/models/safety.py`
  - `backend/app/models/safety_profile.py`
  - `docs/safety-automation/README.md`
