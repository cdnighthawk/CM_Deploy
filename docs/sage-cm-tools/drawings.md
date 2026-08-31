# Drawings

Status: complete
Sage CM module: Drawings / Specifications / ITB (Lead or Project Library)
Official help: https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/Drawings/DrawingsOverview.htm

## Purpose

The drawing log tracks plan sheets and revisions for a lead or project. Each record has a drawing number, title, discipline, drawing set, and date, plus a linked CAD/PDF/TIFF/JPEG file. Lists show the **latest revision** (same Drawing #, later date). Files are shared through ITB, RFP, and referenced on CPRs, COs, SCOs, RFIs, submittals, and work orders.

## Where it lives

- Lead or Project Home → **Drawings** (Project Library / Lead Library)
- Views: Simple List and Card Style (thumbnail only if a file is linked)
- Also created in Add Lead / Add Project wizards
- Mobile and TeamLink: standard listing of **latest** drawings (read)
- Browser: latest on Simple Listing and Card Style

## Who uses it

- Estimators and PMs upload and burst PDFs
- Administrators configure disciplines in Feature Settings → Drawings
- Bid captains link sheets to ITB
- External vendors view granted files in TeamLink

## Prerequisites

- Lead or project exists
- Disciplines configured (architectural, civil, electrical, etc.)
- Revisions **must reuse the original Drawing Number** with a later date
- Multi-structure projects: optional Prime Contract on each drawing
- Upload: up to 48 files per drop, **500 MB** total; PDF preferred

## What the user fills out

### Add Manually

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Lead or Project # | No | Lookup | Prefilled from context |
| Prime Contract | No | Lookup | Projects with multiple structures/lots |
| Drawing Set | Yes | Choice | **New Drawing Set** (date + Drawing Set Name) or **Existing Drawing Set** |
| Files | Yes | PDF, TIFF, DWG, DXF (JPEG also in overview) | Drag/drop or Add |
| Discipline | No | Lookup | Per record; Feature Settings → Drawings |
| Burst | No | Action | Multi-page PDF → one drawing record per page |
| Drawing # | No | Text | Editable after upload; import max 25 characters |
| Title | No | Text | Import max 255 characters |
| Release Date | No | Date | Import required as `ReleaseDate` |

### Excel import (metadata only — files uploaded later)

Search snippet for Import Drawing Log (page later 404’d; fields from official search extract):

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| DrawingNum | Yes | Text | Max 25 characters |
| ReleaseDate | Yes | Date | DD-MMM-YYYY, MM-DD-YYYY, or YYYY-MM-DD |
| Title | Yes | Text | Max 255 characters |
| Description | No | Text | Max 500 characters |
| Discipline | No | Text | Must match configured disciplines |

If the import page is republished, reconfirm Description/Discipline. Treat any other import columns as **not confirmed in help**.

### Other manage actions (overview)

- Group by discipline or revision
- Create a drawing set
- Add addendums
- Add a revision
- Update multiple drawings at once

Exact extra fields on addendum/revision dialogs beyond Drawing # + later date: **not confirmed in help**.

## What Sage CM saves

- Header record: drawing log row (number, title, description, discipline, set, release date, optional prime)
- Line / child records: revisions (same number, later date); addendums; linked file
- System-generated values (IDs, numbers, dates, totals): thumbnail for Card view; “latest” flag by number + date
- Files / attachments: one (or more) linked files; processed for Document Viewer/annotations on first View (file management: up to ~30 minutes)
- Audit / workflow fields: not confirmed in help

## Statuses and lifecycle

No draft/approved drawing status in help. Lifecycle is **original set → revisions/addendums**. UI always prefers the latest sheet.

## Dates that drive alerts

**Release Date** / drawing set date are stored. They are **not** listed on the Home alerts feature table.

## Relationships

- Upstream: lead/project; optional prime contract; drawing set
- Downstream: ITB, RFP, Bid Notifications (coming soon per help), CPR/CO/SCO/RFI/submittal/WO references

## Reports and exports

- Drawing log Excel import (no files)
- Link into ITB/RFP
- Project file download (All Project Linked Files)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Drawing file + sheet metadata | `documents` + `drawings` / `backend/app/models/document.py` | implemented |
| Drawing set | `drawing_sets` / `backend/app/models/drawing_set.py` (lead-scoped) | partial |
| Revisions | `drawing_series_id`, `revision`, `GET /api/v1/drawings/<id>/revisions` | implemented |
| Hygiene / labels | `_drawing_hygiene.py`, `label_status`, `sheet_function` | implemented |
| Project drawings API | `GET/POST /api/v1/projects/<id>/drawings` | implemented |
| Viewer | `construction/drawing-viewer.html` | implemented |
| Discipline settings / Burst / ITB link | none as Sage drawing log | none |
| Prime contract on drawing | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/Drawings/DrawingsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/Drawings/DrawingAddManually.htm
  - https://help.sagecm.intacct.com/Content/Modules/DwgsSpecsITB/DrawingLog/DrawingLogOverview.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - Import field extract: https://help.sagecm.intacct.com/Content/Modules/Import/ImportDrawingLog.htm (fetch later returned 404)
- Local files reviewed
  - `backend/app/models/document.py`
  - `backend/app/models/drawing_set.py`
  - `backend/app/api/v1.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/drawing-viewer.html`
