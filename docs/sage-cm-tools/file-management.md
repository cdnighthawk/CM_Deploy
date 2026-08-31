# File management

Status: complete
Sage CM module: Online File Management (platform)
Official help: https://help.sagecm.intacct.com/Content/Modules/FileManagement/FileManagementOverview.htm

## Purpose

Online File Management is how Sage attaches **external files** (PDF, CAD, photos, Office, etc.) to **any record**, processes them for the Document Viewer and annotations, controls who can see them, shares them in TeamLink, and optionally sends them to **DocuSign**. Project-level browse/download is `project-files-library.md`; this tool is the **platform rules and per-record Linked Files** behavior.

## Where it lives

- **Linked Files** section on almost every feature record (list in UploadingFilesFromFeature)
- Lead/project **Linked Files** tab
- Document Viewer (browser popups must be allowed)
- TeamLink: Grant Access / Show In Portal; externals can **upload**
- DocuSign integration (eSign overview — companion product)
- Mobile: link files, download, viewer highlight/notes

## Who uses it

- Anyone who can edit a record (upload up to 10 files at once from a feature form)
- Administrators (all files)
- Non-admins with the **access all uploaded files** checkbox on the user (Settings)
- External TeamLink users when granted

## Prerequisites

- Storage: included on Max Employee plans (quota by plan); Individual License plans must purchase storage
- File size ≤ **500 MB** and within remaining storage
- **No .EXE**
- Filename ≤ **100 characters**; spaces and unsupported characters → `_`
- Same lead/project only for Link Existing
- Viewer: first **View** triggers processing (minutes, up to ~30 minutes)

## What the user fills out

### Upload on a record (up to 10 at once; RFP wizard allows 48 / 500 MB)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Add / Drag files here | No | Files | Any type except EXE |
| Link Existing | No | Choice | Drawings & Specs; Photos; All Other Records |
| Feature Name | No | Lookup | When All Other Records |
| Album | No | Lookup | When Photos |
| Grant Access | No | Checkbox | TeamLink / portal |
| Show In Portal | No | Checkbox | Photo albums (TeamLink defaults) |

### Features that officially list Linked Files

Drawings; Specifications; Project or Lead Directory; Estimates; Prime Contracts; Allowance Packages; CPRs; COs; Prime Invoices; RFPs; POs; PO COs; Bills; Subcontracts; SCOs; Sub Invoices; Issues; Journals; RFIs; Submittals; Transmittals; Daily Logs; Meetings; Work Orders; Checklists; Comply Notices; Permits; Punchlist Items; Tests/Inspections; Safety Incidents; Safety Meetings; Site Hazard Assessments.

### Viewer / annotate

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| View | No | Action | Starts processing; then annotations |
| Highlights / notes | No | Annotation | Mobile and browser viewer |

Exact annotation tool names beyond highlight/notes: **not confirmed in help**.

### Permissions (Settings, not the file row)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Access all uploaded files | No | Checkbox | On the user when role is not administrator |

## What Sage CM saves

- Header record: file metadata (sanitized name, size, feature, parent record)
- Line / child records: annotations after viewer processing; Grant Access flag
- System-generated values (IDs, numbers, dates, totals): processing state for viewer
- Files / attachments: blob in online storage
- Audit / workflow fields: admin vs granted vs record-scoped access; DocuSign envelope if eSign used

## Statuses and lifecycle

Upload → (optional) viewer processing → viewable/annotatable. No draft/approved file status in help. Email “Email Upload Attachments” are **not** stored on the record.

## Dates that drive alerts

None on the file itself.

## Relationships

- Upstream: any listed feature record
- Downstream: TeamLink, ITB/RFP Grant Access, DocuSign, All Project/Lead Linked Files download

## Reports and exports

- View and download all lead files / all project files
- Download All Photos (email ZIP)
- Share via TeamLink

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| File blob + metadata | `documents` (`file_url`, `original_filename`, `mime_type`, `file_size_bytes`, `version`) | partial |
| Drawing annotations | `drawing_annotations` | implemented |
| Submittal PDF annotations | `documents` + submittal annotation routes | partial |
| Correspondence files | `correspondence_items` | partial |
| Grant Access / TeamLink / DocuSign / 500 MB rules | none as Sage file platform | none |
| Files UI | `construction/files.html` | stub |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/FileManagementOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/UploadingFilesFromFeature.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/LinkingExistingFiles.htm
  - https://help.sagecm.intacct.com/Content/Modules/FileManagement/DownloadProjectFiles.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileAppOverview.htm
- Local files reviewed
  - `backend/app/models/document.py`
  - `backend/app/models/correspondence.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/files.html`
