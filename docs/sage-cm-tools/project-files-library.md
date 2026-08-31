# Project files library

Status: complete
Sage CM module: Projects — General Info / Project Library
Official help: https://help.sagecm.intacct.com/Content/Modules/FileManagement/DownloadProjectFiles.htm

## Purpose

**All Project Linked Files** is the cross-feature file cabinet for one project: every file already attached to drawings, specs, photos, contracts, RFIs, etc. The **Project Library** menu entries (**Drawings**, **Specifications**) are the structured logs; this tool is the **flat download/search** surface plus lead/project Linked Files.

## Where it lives

- Project Home → **All project files** / **All Project Linked Files** (General Info)
- Project Home → **Project library** → Drawings, Specifications
- Lead Home → equivalent lead library + lead linked files
- Lead or project record → **Linked Files** tab (upload or Link Existing)
- Mobile: download/view in the document viewer
- TeamLink: files with Grant Access / Show In Portal

## Who uses it

- PMs download a ZIP-like set of job files
- Estimators pull drawings/specs from the library
- External users open granted files in TeamLink

## Prerequisites

- Files must already be uploaded to a **record on the same lead/project** to appear in Link Existing
- Download filters by Feature Name and search (record number or document name)

## What the user fills out

This is mostly a **browser**, not a create form. User controls:

### All Project Linked Files

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Feature Name | No | Lookup | Filter by originating feature |
| Search | No | Text | Record number or document name |
| Download All / Download Selected / row Download | No | Action | |

### Linked Files tab on lead/project

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Drag files here / Add | No | Files | Spaces and unsupported characters → `_` |
| Link Existing | No | Choice | Drawings & Specs; Photos; All Other Records |
| Feature Name | No | Lookup | Only features that already have linked files |

### Photos bulk download (related)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Actions → Download All Photos | No | Action | Email with ZIP link |

Drawing/spec **create** fields are documented in `drawings.md` and `specifications.md`.

## What Sage CM saves

- Header record: none new — this view aggregates existing linked-file rows
- Line / child records: file links (feature, record #, document name)
- System-generated values (IDs, numbers, dates, totals): filename sanitization
- Files / attachments: the blobs themselves (see `file-management.md` for 500 MB / no EXE / storage plan)
- Audit / workflow fields: Grant Access / Show In Portal on the source record

## Statuses and lifecycle

No library status. Files stay with their source records. Deleting a source record’s effect on the aggregate list is **not confirmed in help**.

## Dates that drive alerts

None.

## Relationships

- Upstream: every feature that accepts Linked Files
- Downstream: ITB/RFP linking, TeamLink, email Grant Access

## Reports and exports

- Download All / Selected
- Export project data (CSV) is a separate Reports path
- Download All Photos (email ZIP)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Polymorphic files | `documents` / `backend/app/models/document.py` | partial |
| Project files page | `construction/files.html` | stub |
| Drawing files API | `/api/v1/projects/<id>/drawings`, `/drawings/<id>/file` | implemented |
| Correspondence archive files | `correspondence_items.storage_relpath` | partial |
| Feature-name filter + Download All | none as Sage aggregate cabinet | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/DownloadProjectFiles.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/LinkingExistingFiles.htm
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectExportingData.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
- Local files reviewed
  - `backend/app/models/document.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/files.html`
