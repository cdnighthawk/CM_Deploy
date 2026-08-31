# Projects

Status: complete
Sage CM module: Projects
Official help: https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectAddManually.htm

## Purpose

A project is an **awarded job**. Create it manually or with the Lead to Project wizard. After save, the Project Home menu unlocks the full product: directory, drawings/specs, ITB, estimates, contract admin, procurement, time, correspondence, documentation, QC/safety, and scheduling.

## Where it lives

- Global nav: **Projects** list + Project Insights (Active Projects)
- Record: **Project Home** (open items at top; menu listed in October 2023 release notes)
- Create: Actions → Add Manually (multi-step wizard)
- Mobile: project title and address read/edit; most field modules available
- TeamLink: project-scoped roles (Owner, Architect, Vendor, custom)

## Who uses it

- PMs and administrators create projects
- Accounting sets currency, retainage, prime contract, and job cost codes
- Estimators may still add estimates/ITB on an awarded project
- Field staff work from Project Home and mobile

## Prerequisites

- Optional: latest drawings/specs in PDF
- Optional: lead/project classifications in Feature Settings → Lead / Project
- Optional: Excel of cost codes and budgets (contract amount, cost, labor hours, equipment hours)
- Customer company/contact new or existing
- **Specify Contacts for Project** and **Show Only Specified Contacts on Add/Edit Forms** cannot be changed after create
- Project # is not auto-generated (max 25 alphanumeric). Sage 100 Contractor AccountingLink: numbers only, no leading zero
- Currency locks after a prime contract is posted (admins can still change)

## What the user fills out

### Step 1 — Customer

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| New vs Existing Customer | Yes | Choice | |
| Company Name / First / Last | Conditional | Text | New Customer |
| Display Name | Yes | Text | Auto First + Last |
| Email | Recommended | Email | |
| Default Tax Code / Payment Terms | No | Lookup | Terms used on prime invoices |
| New Contact / Existing Contact | No | Choice | |

### Step 2 — Number, title, currency, address, stakeholders

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project # | Yes | Text | Max 25 alphanumeric; not auto-numbered |
| Project Title | Yes | Text | |
| Currency | Yes | Lookup | Locked after prime posted |
| Bid Due Date and Time | No | Date/time | Available on ITB and RFP |
| Sales Contact / Bid Contact / Project Manager | No | Lookup | Workflow approvals and alerts |
| Est. Start Date / Est. Finish Date | No | Date | |
| Project Address | No | Address | |
| Specify Contacts for Project | No | Checkbox | Directory only shows companies that have contacts. **Immutable after create** |
| Show Only Specified Contacts on Add/Edit Forms | No | Checkbox | Correspondence/docs pickers limited to directory. **Immutable after create** |

### Step 3 — Classifications

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Classification options | No | Lookups | One per classification in Feature Settings |

### Steps 4–8 — Drawings, specs, photos

Same as the lead wizard: drawing set date/name, files, Burst, Drawing #/Title/Discipline; Specification #/Title; JPEG/TIFF/BMP photos.

### Steps 9–11 — Job cost codes, prime contract, budgets (optional)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Cost-code source | No | Choice | No; Excel import; Sage CM sample JCC templates; Master Cost Code List |
| Prime Contract # | Conditional | Text | Default available |
| Contractor Company / Contact | Conditional | Lookup | Typically your firm / PM or officer |
| Contract Type | Conditional | Lookup | Fixed Lump Sum, Cost Plus (with/without GMP), Unit Price — drives invoices and budgets |
| Work Subject | No | Text | |
| Issue Date | No | Date | Defaults to today |
| Status / Status Date | No | Status / date | Pending if workflow applies; if approved, set a status date |
| Prime Retainage % / Sub Retainage % | No | Percent | Completed work; stored materials only on lump sum |
| Division/Major/Minor/Subminor selection | Conditional | Lookup | One level per wizard pass if using master list |
| Cost budgets and contract (revenue) amounts | No | Currency | SOV / bank draws |

## What Sage CM saves

- Header record: project #, title, currency, address, bid due, stakeholders, contact-restriction flags, classifications, est. dates
- Line / child records: drawing log, specs, photos, optional prime contract, job cost codes, original budgets
- System-generated values (IDs, numbers, dates, totals): project ID; prime # default; today’s issue date
- Files / attachments: library files from the wizard
- Audit / workflow fields: prime status Pending until workflow approve/reject; currency lock after prime posted

## Statuses and lifecycle

Project list uses Active / archived (reactivate for reports). Lead conversion requires **Awarded**. Prime contract: **Pending** → approved (status date required when approved). Closed/archived projects drop off calendars and alerts.

USIS uses a different enum (`planning`, `active`, `on_hold`, `complete`, `archived`, `cancelled`).

## Dates that drive alerts

- Owner **Bid Due Date** when the user is Bid, PM, or Sales Contact
- Child modules add their own due dates (see `alerts.md`)

## Relationships

- Upstream: customer company; optional awarded lead
- Downstream: every project-scoped module (directory, estimates, contracts, procurement, correspondence, etc.)

## Reports and exports

- Project Home → Reports; Project Specific Reports in Reports module
- Export project data to CSV (admin; Single Project & Prime option)
- All Project Linked Files download
- Photos → Download All Photos (ZIP link by email)

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Project header | `projects` / `backend/app/models/project.py` | implemented |
| Number, name, address, dates, contract value | `number`, `name`, `address_*`, `start_date`, `substantial_completion_date`, `contract_value` | implemented |
| Status | `project_status` enum | partial |
| GC / owner / architect FKs | `gc_company_id`, `owner_company_id`, `architect_company_id` | partial |
| Sage project id | `sage_project_id` | partial |
| Project CRUD | `GET/PATCH /api/v1/projects`, `POST /api/v1/projects/bulk` | implemented |
| Project UI | `construction/projects.html`, `construction/project-detail.html` | implemented |
| Add Project wizard (contacts flags, prime, JCC, currency lock) | none as Sage wizard | none |
| Prime contract in-wizard | `project_contracts`, `prime_contract_sov_lines` | partial |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectAddManually.htm
  - https://help.sagecm.intacct.com/Content/GettingStarted/Definitions.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
  - https://help.sagecm.intacct.com/Content/Modules/Projects/ProjectExportingData.htm
- Local files reviewed
  - `backend/app/models/project.py`
  - `backend/app/api/v1.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/projects.html`
  - `W3CRM-v3.0-13_September_2025/gulp/src/construction/project-detail.html`
