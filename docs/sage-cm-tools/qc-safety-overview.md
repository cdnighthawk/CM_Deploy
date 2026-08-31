# QC and safety overview

Status: complete
Sage CM module: QC and Safety
Official help: https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_FieldPM_04_QC_Safety.htm

## Purpose

QC and Safety Overview is the project hub for quality control (checklists, comply notices, permits, punchlist items, tests/inspections) and safety (site hazard assessments, safety incidents, safety meetings). Implementation starts with Feature Settings → QC & Safety, then this overview, then the popular tools (checklists, punchlists, incidents, safety meetings). Two calendars sit here: Quality Control Calendar and Safety Calendar.

## Where it lives

- **Project Home** → QC and Safety section → **QC and Safety Overview**.
- Child lists also appear as Quality Control vs Safety subsections (help sometimes says “Quality Control section” vs “Safety section”).
- **Lead Home** also exposes checklists and site hazard assessments (add pages allow lead or project).
- **Quality Control Overview → Quality Control Calendar**; **Safety Overview → Safety Calendar** (also reachable from Home Alerts).
- **Team Open Items** on Quality and Safety overview pages (Related Functions).
- **Mobile:** Checklists, Comply notices, Permits, Punchlist items, Tests/inspections, Site hazard assessments, Safety incidents, Safety meetings (see `mobile-apps.md` for R/E/A/D).
- **TeamLink:** External collaborators **cannot** view checklists or checklist items. Punchlist/comply follow-up can go through open-items email.

## Who uses it

- Superintendents and PMs run checklists, punch walks, permits, and SHA.
- QC coordinators issue comply notices and log tests/inspections.
- Safety staff record incidents, toolbox/safety meetings, and hazard items.
- Inspectors and responsible contractors are directory companies (not always Sage users).
- Admins configure types/statuses/hazard catalogs in Feature Settings → QC & Safety.

## Prerequisites

- Project (or lead for checklists / SHA).
- Settings → **Feature Settings → QC & Safety**: permit types (required on add), permit statuses, test/inspection types, site hazard item catalog, other QC/Safety lists.
- Settings → **Templates & Reports → Checklist Templates** for reusable QC checklists.
- Responsible / issued-to / recorded-by / inspector companies in the **project directory**. Building department for permits does **not** need to be in the directory.
- Review implementation plan step 1 before first production use.

## What the user fills out

The overview is not a create form. Users:

| Action | Fields |
|---|---|
| Open QC or Safety calendar | Feature checkboxes / filters (same pattern as project Alerts) |
| Team Open Items | Company + optional Contact; review item #s; Send Email |
| Navigate to a tool | No overview fields |

### Quality Control open items (email)

| Feature | Filter criteria |
|---|---|
| Comply notice | Status = Open; Issued To = selected company/contact; Response Date is null |
| Punchlist item | Status = Open; Responsible = selected company/contact; Completion Date is null |
| Test and inspection | Test Overall Status = Open; Sample Test Status = Pending; Testing Company = selected company/contact |

Checklists are **not** in the open-items table. Checklist items alert as **one** Home Alerts row: Date = earliest item due date; Subject = checklist name.

### QC / Safety alert dates

| Feature | Date |
|---|---|
| Checklist inspection | Review date |
| Checklist item | Due date |
| Comply notice | Response due date; Date responded |
| Permits | Expire date |
| Punchlist inspection | Inspection date |
| Punchlist item | Due date |
| Safety meeting discussion item | Due date |

Site hazard assessments and safety incidents are **not** listed on the alerts-date table.

## What Sage CM saves

- **Header record:** None for the overview. Child tools persist their own headers (see sibling files).
- **Line / child records:** Checklist items, punchlist items, SHA items, incident injuries/damage/witnesses, test samples, meeting attendees/items.
- **System-generated values:** Record numbers (Comply Notice #, Permit Application #, Punchlist Item #, Test #, Assessment #, Safety Meeting #).
- **Files / attachments:** Linked files on Checklists, Comply Notices, Permits, Punchlist Items, Tests/Inspections, Safety Incidents, Safety Meetings, Site Hazard Assessments (upload-from-record list).
- **Audit / workflow fields:** Feature Settings catalogs; Team Open Items hyperlink + security code.

## Statuses and lifecycle

Overview has no status. Child lifecycle (confirmed):

| Tool | Confirmed statuses |
|---|---|
| Comply notice | Open (until Response Date set) |
| Punchlist item | Open → Closed (+ Completion Date) |
| Test / inspection header | Overall Status Open (open items) |
| Test sample | Pending (default), Compliance, Non-Compliance |
| Permit | Configurable Status + Status Date (Feature Settings) |
| Checklist item | Checked date / due date (no Open/Closed name in help) |
| SHA item | Estimated / actual completion dates |
| Safety meeting item | Due date while open (alerts) |

## Dates that drive alerts

See table above. Also: comply Response Due Date is marked on the Quality Control Calendar and Home Alerts (comply add help).

## Relationships

- **Upstream:** Feature Settings QC & Safety; project directory; prime contract on most add forms; drawings/specs/photos for links.
- **Downstream:** QC Calendar, Safety Calendar, Team Open Items, mobile field updates, detail/log reports, Word merge templates (e.g. SafetyAccident.dot).
- **Do not confuse:** Punchlist items (project-specific defects) vs Checklist items (reusable internal QC process). SHA vs Daily Pretask (USIS-only).

## Reports and exports

- Implementation plan links training videos (some still branded Corecon).
- Per-tool log/detail reports (punchlist open-item log; multi-project safety incident logs Apr 2025).
- Download checklist; download/print permit; print safety incident.

## USIS / CM_Deploy mapping

USIS safety is Cal/OSHA packet + daily pretask + playbook checklists, not a Sage QC/Safety overview.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| QC and Safety Overview / calendars | none | none |
| Feature Settings QC & Safety catalogs | none | none |
| Team Open Items (QC) | none | none |
| Company/project safety packet | `company_safety_profiles`, `project_safety_profiles`, `project_safety_packets`; `docs/safety-automation/` | implemented (different product) |
| Safety hub UI | `usis-safety.html`, `GET /api/v1/safety/summary` | partial |
| Playbook checklists | `checklist_templates` / `checklist_runs` | partial (ops playbooks, not Sage QC checklists) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_FieldPM_04_QC_Safety.htm
  - https://help.sagecm.intacct.com/Content/Modules/Emailing/OpenItemsEmail.htm
  - https://help.sagecm.intacct.com/Content/Modules/AlertsCalendars/AlertsCalendar_All.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/UploadingFilesFromFeature.htm
- Local files reviewed
  - `docs/safety-automation/README.md`
  - `backend/app/models/safety.py`
  - `backend/app/models/safety_profile.py`
  - `backend/app/models/playbook.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/usis-safety.html`
