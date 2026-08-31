# Procurement Overview

Status: complete
Sage CM module: Procurement
Official help: https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Financials_02_POs_Subcontracts.htm

## Purpose

Procurement Overview is the project hub for buyout after the prime is approved. It is the implementation-plan checkpoint before creating POs and subcontracts: confirm Feature Settings, project directory vendors, then issue commitments. Sage splits buyout into **POs** (no retainage; vendor invoices via Bills / PO-to-Bill) and **subcontracts** (retainage, SCOs, sub invoices). Both become **Committed Cost** in Project Analytics only when **Approved with a status date**.

## Where it lives

- Project menu → **Procurement** → **Procurement overview**
- Hub / overview, not a single transaction form
- Implementation plan step 02.1-3: open this page after reviewing Settings → Feature Settings → Procurement
- TeamLink: vendors see approved POs / PO COs / related procurement under Project Home → Procurement; they do not use this GC overview

## Who uses it

- PMs and procurement staff verify directory and then jump to POs, RFPs, subcontracts
- Financial staff confirm committed vs billed from the sibling financial-information pages
- Admins configure PO types, bill types, anticipated-cost method, duplicate invoice check, and “do not modify after sub invoices”

## Prerequisites

- Prime **Approved with a status date** (hard gate for POs and subcontracts)
- Job cost codes on the project (required on commitment lines)
- Vendors in the **project directory**
- Optional: PO types, bill types, tax codes, numbering, workflow rules
- Review Feature Settings → Procurement (anticipated cost method; retainage/modification locks; duplicate invoice numbers)

## What the user fills out

The overview does not persist a record. Users read counts/links and navigate. Documented adjacent actions:

| Field / control | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Current project | |
| Prime Contract | Implicit | Approved prime | Required before any PO/subcontract |
| Project Directory count | n/a | Link | Implementation plan: verify suppliers/subs are listed |

Links on the same Procurement menu (not fields): RFPs, Anticipated costs, POs, PO COs, Bills, Subcontracts, SCOs, Subinvoices, PO financial information, Subcontract financial information.

## What Sage CM saves

Nothing unique to the overview. Child tools persist POs, subcontracts, bills, etc.

## Statuses and lifecycle

No overview status. The procurement **family** status that unlocks committed cost is the same on POs, subcontracts, SCOs, and PO COs:

**Draft → Pending Submission → Pending → Not Approved → Approved**

**Committed cost = Approved + status date.** Pending amounts may appear in analytics as Pending / ApprovedAndPending totals but are not “committed” in the sense Sage uses for job-cost dashboards.

Bills and sub invoices use **Approved checkbox** (pending if unchecked). Only approved bills/sub invoices are cost-to-date and AccountingLink-exportable.

## Dates that drive alerts

None on the overview. See PO Reminder Date, RFP Bid Due, subcontract start/finish, bill Payment Due.

## Relationships

- Upstream: Approved prime; job cost codes; project directory; optional estimate RFPs
- Downstream: All Procurement record tools and Project Analytics committed / cost-to-date
- P2P: workflow rules lock a transaction while initiated/approved unless abandoned (`workflow_rule_active` in USIS)

## Reports and exports

- No dedicated overview report in help
- Project Analytics transaction-type API: PO_*, Bill_*, Subcontract_*, SCO_*, SubInvoice_*
- AccountingLink for bills and sub invoices

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Procurement overview hub | `usis-procurement.html` + `project-detail-procurement.js` | partial |
| PO + subcontract commitments | `commitments` / `/api/v1/projects/{id}/commitments` | partial |
| Project directory for vendors | `project_directory_companies` | partial |
| PO types | `procurement_po_types` | partial |
| Feature settings / overview metrics | none | none |

## Sources

- Official Sage help URLs used
  - https://help.sagecm.intacct.com/Content/GettingStarted/ImplementationPlan_Financials_02_POs_Subcontracts.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/POs/POsOverview.htm
  - https://help.sagecm.intacct.com/Content/Modules/Procurement/Subcontract/SubcontractOverview.htm
  - https://help.sagecm.intacct.com/Content/ReleaseNotes/October-2023/oct-23-projects-menu.htm
- Local files reviewed
  - `Plan/22. Sage_CM_subcontracts_SCO_and_P2P_alignment.txt`
  - `backend/app/models/commitment.py`
  - `backend/app/models/procurement.py`
  - `W3CRM-v3.0-13_September_2025/gulp/src/usis-procurement.html`
