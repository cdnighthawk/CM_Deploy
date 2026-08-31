# Excel add-in

Status: complete
Sage CM module: Companion products
Official help: https://help.sagecm.intacct.com/Content/IntegrationsPublicAPIs/MicrosoftOffice/SCMExcelAddIn/SCMExcelAddInOverview.htm

## Purpose

The Microsoft Excel add-in (**Sage Construction Management Connect**) exports **job cost / financial API** data into a chosen workbook sheet and cell via the Sage CM **Open API**. Users pick one or more projects, API version (V1, V2, or V3), optional transaction date filters, and Fetch Data. It is not a general CRUD add-in for daily logs or punchlists.

## Where it lives

- Installed inside **Microsoft Excel** (desktop add-in), not on Project Home.
- Requires the **Open API** option: **free** on Sage CM Max Employee License Plan; **additional fee** for individual licenses.
- Credentials are generated in Sage CM (account ID, client ID, secret key) and pasted into the add-in.
- Direct fetch of `SCMExcelAddInOverview.htm` without TocPath returned **404** in this pass; field list below is from the official help search/index snippet for that same topic (retry + search). Treat any UI label not in that snippet as **not confirmed**.

Related but **different** Excel features: schedule import from Excel; punchlist Excel import; estimate Excel import; AccountingLink WIP Excel import. Those are not this add-in.

## Who uses it

- Accounting / PM staff building job-cost workbooks.
- The **client ID is organization-wide and gives full admin access** — treat as a secret; limit who installs the add-in.

## Prerequisites

- Open API entitlement (Max plan or paid add-on).
- Account base URI, account key (Account ID), integration key / client ID, secret key generated in Sage CM.
- Excel with the add-in installed and **Save Keys and Submit** successful (then **Sign Out** appears).

## What the user fills out

### Generate API credentials (in Sage CM)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Account ID / account key | Yes | Secret | Organization account |
| Client ID / integration key | Yes | Secret | **Full admin access** for the org |
| Secret key | Yes | Secret | |

Exact Settings navigation to generate keys is **not confirmed** beyond “generate the account ID, client ID, and secret key for the API connection.”

### Connect the add-in

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Base URL | Yes | URI | Account base URI |
| Account ID | Yes | Text | Account key |
| Client ID | Yes | Text | Integration key / client ID |
| Secret Key | Yes | Text | Secret key |
| Save Keys and Submit | Yes | Action | Then Sign Out appears on success |

### Fetch financial data

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| API Name | Yes | Dropdown | Sage Construction Management API **V1, V2, or V3** |
| Project (filter text) | No | Text | Filters the project listing |
| Projects | Yes (one or more) | Multi-select | |
| Start Date | No | Date | Transaction filter |
| End Date | No | Date | Transaction filter |
| Sheet Name | Yes | Excel sheet | Target sheet |
| Cell Number | Yes | A1-style | Where financial data is populated |
| Fetch Data | Yes | Action | Then Ok |

Help: “All fields retrieved from the API will be populated in Excel.” Column list is **API-version-specific** and **not enumerated** on the overview snippet.

## What Sage CM saves

- **Header record:** None in SCM. The add-in writes into the workbook.
- **Line / child records:** API financial rows (job cost) as Excel cells.
- **System-generated values:** API payload fields (version-dependent).
- **Files / attachments:** The `.xlsx` is local; not a Sage linked file.
- **Audit / workflow fields:** Keys stored in the add-in after Save Keys; Sign Out disconnects.

## Statuses and lifecycle

1. Entitled Open API → generate keys.
2. Install add-in → enter Base URL + three secrets → Save Keys and Submit.
3. Select API version, projects, dates, sheet, cell → Fetch Data.
4. Sign Out when done.

No draft/approved workflow.

## Dates that drive alerts

None. Start/End Date are fetch filters only.

## Relationships

- **Upstream:** Open API, project financials (same family as AccountingLink job-cost data, but Excel is a pull into a spreadsheet).
- **Downstream:** User workbooks, pivot tables, WIP models.
- **Not:** Gantt Excel import, punchlist Excel import.

## Reports and exports

The add-in **is** the export path. Official statement: job cost information exported to the target sheet and cell; all API fields populated.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Excel Connect add-in | none | none |
| Open API V1/V2/V3 job cost | none | none |
| USIS REST APIs | Flask `/api/v1/...` | none (different product) |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/IntegrationsPublicAPIs/MicrosoftOffice/SCMExcelAddIn/SCMExcelAddInOverview.htm
  - https://help.sagecm.intacct.com/Content/IntegrationsPublicAPIs/MicrosoftOffice/SCMExcelAddIn/SCMExcelAddInOverview.htm?TocPath=Integration%7C_____1 (404 on raw fetch; content taken from help index/search)
- Local files reviewed
  - No USIS equivalent
