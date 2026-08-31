# Reports (standard and custom log reports + detail templates)

Status: complete
Sage CM module: Reporting
Official help: https://help.sagecm.intacct.com/Content/Modules/Reporting/LogReports/ResourceCenter_LogReports.htm

## Purpose

Sage reporting is three layers: **detail reports** (Word mail-merge of one record), **log reports** (column/row lists of many records, standard or custom, PDF/Excel), and **BI dashboards** (separate file). This tool is the Reports module plus Print/Reports on a record. Custom logs use shared SQL views (e.g. vw_ProjectInfoSimple) and a tablix designer.

## Where it lives

- Global nav: Reports → Report Category / Sub-Category → standard or Custom Reports tab.
- Feature or module landing pages also launch the same logs.
- On a saved record: Reports → format + template → PDF/DOC/DOCX, Save to Linked Files, or Email.
- Admin: upload corporate logo; upload Word .dot templates by feature category.
- Not TeamLink-authored. Portal users may receive emailed PDFs.

## Who uses it

Roles with Reports / Analytics / the underlying feature. Custom log design is typically an administrator. Detail print is anyone who can open the record.

## Prerequisites

- Data in the feature (and logo if branding logs).
- For custom logs: familiarity with shared views; save every 5–10 minutes (browser designer can lose work).
- Detail templates uploaded under the correct feature category (e.g. Issue Details).

## What the user fills out

### Print a detail report (from a record)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Report option | Yes | Dropdown | Feature-specific |
| Format | If applicable | Enum | |
| Template | Yes | Lookup | Uploaded Word template |
| Export option | Yes | Enum | PDF; .DOCX; .DOC; Save PDF/DOC to Linked Files; Email DOC; Email PDF |

Save before printing.

### Access / run a log report

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Report Category / Sub-Category | Yes | Lookup | |
| Standard vs Custom tab | Yes | Tab | |
| Project / lead / date parameters | Per report | Mixed | Added in custom design as parameters |

### Create a custom log report (designer)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Add Custom Report | Yes | Action | Custom Reports tab |
| Shared DataSource | Yes | Lookup | CONNECT |
| View (e.g. vw_ProjectInfoSimple) | Yes | Drag from dbo | Do not modify the FROM clause |
| Additional views + join type | No | Enum | Inner, Left outer, Right outer, Full outer |
| Remove unused fields | No | Designer | Delete row/field |
| Parameters | Yes typically | Filter | Project, date range (UTC guidance in advanced help) |
| Header / footer / report properties | Yes | Layout | Logo |
| Tablix | Yes | Table | Columns from the view |
| Expressions / grouping / totals / sort / repeat headers | No | Designer | Advanced topics |
| Visible report parameter filters | No | Examples in help | |
| Copy single-project log → multi-project | No | Action | Official advanced topic |

Standard log families (official headings; individual report titles on the page were truncated in the fetch):

- Project-specific: Project library, Project team, Preconstruction (ITB, Estimate items), Client contract admin, Procurement, Time and Expenses (Labor timecards, Employee miscellaneous expenses), Equipment, Correspondence, Documentation, QC and Safety.
- Lead-specific: Lead library, Project team, ITB, Correspondence, QC and Safety.
- General standard log reports (section exists; names not confirmed in the fetched page).

## What Sage CM saves

- Header record: custom report definition (data source, joins, parameters, tablix, branding).
- Line / child records: none at run time (query results).
- System-generated values: PDF/Excel bytes; files saved to Linked Files if chosen.
- Files / attachments: uploaded logo; uploaded .dot templates; output files on the record.
- Audit / workflow fields: none.

## Statuses and lifecycle

Draft custom report in the browser until saved. Published standard reports are Sage-provided. Detail templates are versioned only by re-upload (not confirmed as a version table).

## Dates that drive alerts

None. Date parameters filter the dataset. Help: display dates in the user timezone; filter ranges in UTC.

## Relationships

- Upstream: all modules’ records and views; company logo; numbering (appears as columns).
- Downstream: email, Linked Files, TeamLink if the saved PDF has Show In Portal.
- Sibling: BI dashboards (Syncfusion Bold BI), project analytics.

## Reports and exports

This tool *is* the export path: PDF, Excel (logs), Word (detail). FLS prime invoice detail templates gained extra mail-merge fields (April 2026 notes) — invoice-specific, not a new designer field.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Reports catalog | `_reports_catalog_service.py` + `reports.html` | partial |
| Estimate summary / quote / door schedule | HTML render routes on lead estimates | implemented |
| PO / client proposal print | commitment render routes | implemented |
| Custom log designer / SQL views | none | none |
| Word mail-merge templates | none | none |
| Power BI tile | catalog `powerbi_dashboard` | stub |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/Reporting/LogReports/ResourceCenter_LogReports.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/LogReports/AddLogReports/AddLogReport_Step_01.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/DetailReportTemplates/DetailReportTemplates_PrintingReports.htm
- https://help.sagecm.intacct.com/Content/Modules/Reporting/DetailReportTemplates/Correspondence/IssuesDetails.htm
- https://help.sagecm.intacct.com/Content/ReleaseNotes/April-2026/April-2026-WhatsNew.htm
- Local: `backend/app/api/_reports_catalog_service.py`, `W3CRM-…/gulp/src/reports.html`
