# Project directory

Status: complete
Sage CM module: Projects (Project Team)
Official help: https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectDirectory/ProjectDirectoryOverview.htm

## Purpose

The project directory is the **job-specific subset** of Contact Management: customer, your firm, architect, engineers, CM, subcontractors, and suppliers. Forms can then pick from this list instead of the whole tenant. Leads have a **lead directory** (prospect and your firm — not subs/suppliers). Lead to Project can copy the lead directory.

## Where it lives

- Project Home → **Project Directory** (Project Team)
- Lead Home → Lead Directory (same idea, smaller population)
- Mobile: project directory listing read/add/delete; company overview status read
- TeamLink: role assigned **per company/contact row** on this list

## Who uses it

- PMs add firms as they award trades
- Administrators assign TeamLink roles and send portal login emails
- Estimators add architect/consultants on the lead directory

## Prerequisites

- Companies exist in Contact Management
- Each company should have at least one contact **with email**
- If **Specify Contacts for Project** was set at create, companies **without contacts** cannot be added
- Inactive companies/contacts and rows already in the directory are hidden from the add picker

## What the user fills out

### Add existing companies

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Actions source | Yes | Choice | Add Companies to Directory from Contact Management; from Bidder List; using Company Types |
| Search | No | Text | |
| Company + Contact | Yes | Multi-select | Add moves them into the directory |

### Add new company to Sage CM and Directory

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company name | Yes | Text | Unique |
| Company Code | No | Text | |
| Business Address, Phone, Fax | No | Text | |
| Remaining company fields | No | See companies.md | |
| Primary Contact | Recommended | See contacts.md | |
| Is Bid Contact | No | Checkbox | ITB / RFP filter |

### TeamLink on a directory row

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| TeamLink Role | No | Lookup | Between company and contact; **saves automatically**. Defaults: Owner, Architect, Vendor (plus custom). Project-only, not leads |
| Send portal login email | No | Action | Overview function |

### Copy from another project

Overview lists **Copy companies and contacts from another project**. Source-project picker field names: **not confirmed in help**.

## What Sage CM saves

- Header record: membership rows (project/lead + company + contact)
- Line / child records: TeamLink role per row
- System-generated values (IDs, numbers, dates, totals): none user-facing
- Files / attachments: directory is a listed feature for linking files on the company-in-directory record
- Audit / workflow fields: automatic save on role change

## Statuses and lifecycle

No directory status. Inactive global companies stay out of pickers. Lead directory copies into project on conversion when the wizard includes that step.

## Dates that drive alerts

None.

## Relationships

- Upstream: Contact Management; project create flags
- Downstream: correspondence pickers (if Show Only Specified Contacts); TeamLink; project groups; ITB/RFP still use Contact Management views but directory is the job roster

## Reports and exports

- View directory list
- TeamLink login email
- Directory is a file-linkable feature

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| User membership (internal) | `project_members` / `backend/app/models/project_member.py` | partial |
| Member API | `GET/PUT /api/v1/projects/<id>/members` | implemented |
| Company directory search/add | `GET/POST /api/v1/projects/<id>/directory/companies` | partial |
| TeamLink role / login email / copy-from-project | none | none |
| Lead directory vs project directory rules | none | none |
| W3CRM directory UI | Members on `project-detail.html`; not a Sage-style directory | stub |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectDirectory/ProjectDirectoryOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectDirectory/ProjectDirectoryAddCompanies.htm
  - https://help.sagecm.intacct.com/Content/TeamLinkPortal/Authentication/TeamLink_Auth2_AssigningSecurityRoles.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Est_01_Leads.htm
- Local files reviewed
  - `backend/app/models/project_member.py`
  - `backend/app/api/_procurement_lookup_service.py`
  - `backend/app/api/_project_members_service.py`
