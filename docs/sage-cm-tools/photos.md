# Photos

Status: complete
Sage CM module: Documentation
Official help: https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos.htm

## Purpose

Photos (help title: Photos and renderings) is the project/lead image library. Users upload jobsite and progress photos, group them into albums, optionally share albums on TeamLink, link photos to other records, and bulk-update location, albums, deletion locks, and feature links.

## Where it lives

- **Lead or Project Home** → Documentation → **Photos**.
- **Albums tab** is the default view (Feb 2025). **Photos tab** lists all photos sorted by date taken descending.
- Photos can also be **linked** onto Daily Logs, Meetings, Work Orders, QC/Safety records, and most other features via Link Existing Files → Photos.
- **Mobile:** Photos R, E, A (max 100 MB per file), D.
- **TeamLink:** album visible only if the photo is in an album **and** the album’s Show In Portal is selected.

## Who uses it

- Superintendents and field staff upload from web or mobile.
- PMs organize albums and set Show In Portal for owners/architects.
- Office staff run Download All Photos and bulk location/album changes.
- External TeamLink users view shared albums only (no internal-employee portal login).

## Prerequisites

- Lead or project exists.
- Image formats: JPG, PNG, TIFF, BMP.
- Web upload: not larger than 500 MB per photo; add-album wizard allows up to 48 files / 500 MB total per batch.
- Mobile upload: not larger than 100 MB; up to 10 photos at a time.
- TeamLink sharing requires the album Show In Portal checkbox and a directory collaborator.

## What the user fills out

### Create album (Actions → Add album)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Album name | Yes | Text | Used for search on the Albums tab |
| Show In Portal | No | Checkbox | Share album + its photos through TeamLink |
| Photo files | No at create | File upload | Drag/drop or Add; JPG/PNG/TIFF/BMP; 48 files / 500 MB per batch |

### Photo attributes (Photos tab search + bulk “global changes”)

Sage documents these as filters and bulk-update fields. Individual caption-editor labels beyond comments/name/location are **not confirmed in help** as a separate form; search treats **names, location, or comments**.

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Location | No | Text | Bulk: select Location checkbox and enter location |
| Comments / name | No | Text | Searchable on Photos tab (Feb 2025) |
| Date Taken | System / EXIF | Date | Default sort descending; filter Start/End Date |
| Date Uploaded | System | Date | Filter option |
| Modified Date | System | Date | Filter option |
| Add To Existing Album | No | Album picker | One photo can belong to multiple albums |
| Add To New Album | No | Text (new album name) | Bulk create + assign |
| Link To Feature | No | Feature + record | Links photo to another project/lead record |
| Prevent Photo Deletion | No | Checkbox | Photos with this set cannot be deleted |
| Clear Prevent Deletion From Selected Photos | No | Checkbox | Bulk unlock |
| Delete Selected Photos From Project and All Albums | No | Checkbox | Permanent delete |

### Share album (Albums tab)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Show In Portal | No | Checkbox | Per album; required for TeamLink visibility |

## What Sage CM saves

- **Header record:** Photo album (name, Show In Portal). Photo file record (image blob + metadata).
- **Line / child records:** Album membership (many-to-many: one photo, many albums). Optional link from photo to another feature record.
- **System-generated values:** Date Taken (from image / camera); Date Uploaded; Modified Date; sort order by Date Taken descending. Unsupported filename characters replaced with `_` on generic file upload.
- **Files / attachments:** The photo **is** the file. Formats JPG, PNG, TIFF, BMP. Web ≤ 500 MB; mobile ≤ 100 MB. Download All Photos emails a ZIP link.
- **Audit / workflow fields:** Prevent Deletion flag; session-stored filter type (Date Taken / Uploaded / Modified); pagination on albums and photos (Feb 2025).

## Statuses and lifecycle

No draft/approved workflow. Lifecycle:

1. Upload photo (web album, Photos tab, mobile, or link-from-record).
2. Optionally assign to one or more albums.
3. Optionally set Show In Portal on albums for TeamLink.
4. Optionally link to a feature record.
5. Optionally set Prevent Deletion.
6. Delete only if Prevent Deletion is clear (or after Clear Prevent Deletion).

## Dates that drive alerts

Photos are **not** listed on the Documentation alerts calendar. Date Taken / Date Uploaded / Modified Date are library filters only.

## Relationships

- **Upstream:** Lead or project; camera/EXIF for Date Taken.
- **Downstream:** Link Existing Files → Photos on Daily Logs, Meetings, Work Orders, Checklists, Comply Notices, Permits, Punchlist Items, Tests/Inspections, Safety Incidents, Safety Meetings, Site Hazard Assessments, and other features in the file-link dialog.
- **TeamLink:** Show In Portal albums.
- **USIS:** field photos can also pin to drawings (`drawing_id`); Sage help does not document drawing pins on the Photos feature itself.

## Reports and exports

- Actions → **Download All Photos**: Sage emails a ZIP download link (confirm three dialogs).
- Photos tab search by name, location, comments; date range filters.
- Linking a photo onto another record includes it in that record’s linked-files / detail report.

## USIS / CM_Deploy mapping

USIS stores jobsite photos and polymorphic documents, not Sage albums or TeamLink Show In Portal.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Photo file | `field_photos`; `documents` (`document_type=photo`) | partial |
| Caption / comments | `field_photos.caption` | partial |
| Location | `field_photos.location_text` | partial |
| Date taken | `field_photos.taken_at` | partial |
| Lat/lon | `field_photos.lat`, `lon` | implemented (Sage help does not list GPS fields) |
| Album / Show In Portal | none | none |
| Prevent Deletion | none | none |
| Link to daily log | `field_photos.daily_report_id` | partial |
| Link to drawing | `field_photos.drawing_id` | implemented (Sage-only equivalent not confirmed) |
| Field photo API | `GET /api/v1/projects/:id/...` via `_field_routes.py` | partial |
| Clock-in/out photo | `time_entries.clock_in_photo_id` / `clock_out_photo_id` | implemented (Sage-only labor clock-in is a different mobile feature) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos_AlbumAdd.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos_PhotoDownloadAll.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos_ApplyGlobalChanges.htm
  - https://help.sagecm.intacct.com/Content/Modules/Documentation/ProgressPhotos/ProgressPhotos_AlbumShowInPortal.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/February-2025/February-2025-WhatsNew-BE-photos-album-improvements.htm
  - https://help.sagecm.intacct.com/Content/Mobile/MobileApp_Apple/MobileApp_AppleiOS_Overview.htm
- Local files reviewed
  - `backend/app/models/field_ops.py`
  - `backend/app/models/document.py`
  - `backend/app/api/_field_routes.py`
