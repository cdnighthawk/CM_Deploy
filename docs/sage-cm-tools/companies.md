# Companies

Status: complete
Sage CM module: Contact Management
Official help: https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Overview.htm

## Purpose

Companies are the first-class firm records in Sage Construction Management’s two-tier contact system (company, then people). Every customer, subcontractor, supplier, architect, and your own firm is stored here so insurance, licenses, bidding lists, project directories, and AccountingLink imports share one unique company name.

## Where it lives

- Global nav: **Contact Management** → **Companies** tab
- Overview / insights: Contact Management Insights row for Companies (add, import, stats)
- Record form: Company Profile (Details, Contacts, Compliance, Classification, TeamLink / externally authorized users)
- Also created inline from the Add Lead / Add Project wizard and from **Project Directory → Add New Company to Sage CM and Directory**
- Mobile: companies are **read-only** in the Sage CM iOS/Android apps
- TeamLink: not a TeamLink module; company contacts can become TeamLink users

## Who uses it

- Administrators and office staff create and import companies during implementation
- Estimators and PMs add vendors while building ITB / RFP bidder lists
- Accounting staff import or link customers/vendors via AccountingLink (Sage 100 Contractor, QuickBooks, Sage 50 Canada, Xero)
- Field staff view address/phone on reports and in the mobile app
- Compliance staff maintain insurance and licenses on the company Compliance tab

## Prerequisites

- Company name must be unique across the tenant
- Optional: payment terms in Settings → Company Settings → Payment Terms
- Optional: tax codes in Settings → Company Settings → Taxation
- Optional: company types and other classification systems in Settings → Feature Settings → Contact Management
- You cannot delete a company until all contacts, insurance records, and project references are removed

## What the user fills out

The Add Manually form only **requires** Company. The Excel import column list is the most complete official field inventory for what Sage persists on the company header. Classification is assigned on a separate Classification tab after save.

### Header / company profile

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes | Text | Unique. Duplicate name errors on save. |
| Company Code | No | Text | Max 25 characters (import: `CompanyCode`) |
| Ship Address 1 / 2 | No | Text | Shipping address. `ShipState` max 15 characters on import |
| Ship City | No | Text | |
| Ship State | No | Text | Max 15 characters on import |
| Ship Postal Code | No | Text | |
| Ship Country | No | Text | |
| Bill Address 1 / 2 | No | Text | Billing address. `BillState` max 15 characters on import |
| Bill City | No | Text | |
| Bill State | No | Text | Max 15 characters on import |
| Bill Postal Code | No | Text | |
| Bill Country | No | Text | |
| Phone | No | Text | Shown on most reports and mobile |
| Phone 2 | No | Text | Import: `Phone2` |
| Fax | No | Text | Shown on most reports |
| Website | No | Text | |
| Default Payment Terms | No | Lookup | Must already exist in Company Settings |
| Default Tax Code | No | Lookup | Must already exist. Typically blank for US clients |
| Gov Id | No | Text | United States: Federal Tax ID |
| Notes | No | Text | No maximum character limit |
| Is Bidder | No | Yes/No | Mark Yes for vendors that regularly receive ITB or RFP emails |
| Active / Inactive | No | Status | Managed after save; inactive companies are hidden from directory pickers |

### Primary contact (created with the company)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| First Name / Last Name | Conditional | Text | Required if you add a contact on the company form |
| Is Bid Contact | No | Checkbox | Filters contacts when adding ITB vendors or RFP package bidders |
| Email | Recommended | Email | Needed for ITB, RFP, TeamLink, and correspondence |
| Business Address, Phone, Fax | No | Text | Can differ from company ship/bill; used for multi-location companies |

### Classification tab

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Classification Type | No | Lookup | Example: Company Types, CSI 95, CSI 2004 |
| Division / Major | No | Lookup | Help states you can assign only Division and Major from the Assign Classifications UI. Import also supports Minor and Subminor columns |
| Business Enterprise classification | No | Lookup | Resource center: MBE, WBE, DBE special classification |

### Related tabs (not the company header)

- **Contacts**: additional people and locations (see `contacts.md`)
- **Compliance**: insurance and licenses (see `company-insurance.md`, `company-licenses.md`)
- **TeamLink / externally authorized users**: portal logins for this firm

## What Sage CM saves

- Header record: one unique company with ship/bill addresses, phones, fax, website, default payment terms, default tax code, Gov Id, notes, Is Bidder, active flag
- Line / child records: contacts (including extra locations), insurance policies, licenses, classification assignments
- System-generated values (IDs, numbers, dates, totals): internal company ID; AccountingLink link when name matches an imported customer/vendor; Last Viewed is not confirmed in help for companies
- Files / attachments: none on the company header itself; insurance and license records accept a Linked File
- Audit / workflow fields: cannot delete while children or project references exist; Active/Inactive; externally authorized TeamLink users

## Statuses and lifecycle

Active → Inactive. Inactive companies are excluded from project-directory and bidder pickers. There is no draft/pending/approved workflow on the company itself. Delete is blocked until contacts, insurance, and project references are cleared.

## Dates that drive alerts

None on the company header. Child insurance and license **Expire Date** values generate Contact Management alerts within 60 days and appear in Team Open Items when expired.

## Relationships

- Upstream: Excel import; Outlook / AccountingLink customer-vendor copy; Add Lead / Add Project wizard (New Customer); Project Directory add-new-company
- Downstream: contacts, insurance, licenses, lead/project directory, ITB vendors, RFP bidders, POs, subcontracts, invoices, TeamLink users

## Reports and exports

- Most standard reports print company address, phone, and fax
- Excel import/export of companies and contacts (Sheet1, Excel 97-2003 `*.xls`)
- Email expired insurance/license notices from the company Actions menu
- AccountingLink can re-link by company name

## USIS / CM_Deploy mapping

What exists in this repo today (models, APIs, pages) and what is still Sage-only.

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Company header | `companies` / `backend/app/models/company.py` | implemented |
| Company type | `companies.company_type` enum (`gc`, `owner`, `architect`, `engineer`, `subcontractor`, `vendor`, `self`, `other`) | partial |
| Ship/bill address, phone, website, tax ID, notes | `address_*`, `phone`, `website`, `tax_id`, `notes` | partial |
| Is Bidder / default payment terms / tax code / fax / second phone | none | none |
| Classification (Company Types, CSI Division/Major) | `trade_specialties` JSONB; no classification engine | stub |
| DBE / prevailing wage flags | `dbe_certified`, `prevailing_wage` | partial |
| Company CRUD API | Module guard lists `/api/v1/companies` as CRM; no dedicated list/create routes found. Used by AI tools and `/api/v1/rfi-companies` | stub |
| Project directory add | `POST /api/v1/projects/<id>/directory/companies` | partial |
| W3CRM company UI | `construction/party.html` (template/stub) | stub |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_Overview.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_AddManual.htm
  - https://help.sagecm.intacct.com/Content/Modules/Import/ImportCompanyContacts.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_AddMultipleLocations.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/Companies/Companies_AssignClassifications.htm
  - https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_ContactManagement_CompanyTypes.htm
  - https://help.sagecm.intacct.com/Content/Modules/ContactManagement/ResourceCenter_ContactManagement.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
- Local files reviewed
  - `backend/app/models/company.py`
  - `backend/app/api/_module_routes.py`
  - `backend/app/api/v1.py` (`/rfi-companies`, directory companies)
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/party.html`
