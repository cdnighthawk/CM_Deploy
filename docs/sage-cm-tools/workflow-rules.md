# Workflow rules

Status: complete
Sage CM module: Administration / Workflow
Official help: https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_Overview.htm

## Purpose

Sage has two workflow products. **Contract Admin & Procurement** rules lock financial transactions and route them to named approvers (or project-manager aliases) when the transaction **value** matches a rule. **Time & Expenses** workflow (5+ licenses) lets managers approve subordinates’ timecards/expenses; it is not a value-threshold rule grid. This file is the rule-definition side. Inbox/approve UI is workflow-alerts-approvals.md.

## Where it lives

- Settings → Workflow → Contract Admin & Procurement (enable + Workflow Rules grid).
- Settings → Workflow → Time & Expenses (enable, strict rules, manager-based approval).
- RFI/Submittal “Response Workflow” (Sequential/Parallel) is **per correspondence record**, not this Settings grid.
- Admin only to define rules. Approvers work from Home → Workflow tab.

## Who uses it

Administrators enable types and add/copy/edit rules. Approvers must already have security-role access to the feature. Feature-based-with-PM-alias also allows system admins and the Project Details project manager.

## Prerequisites

- Decide workflow type **once** (changing type abandons in-progress rules).
- Users/roles exist; Project Details PM filled if using aliases.
- For T&E: 5+ licenses; employee managers set; optional Time Approval Access on user profiles; custom role if PMs need Timecard Approval (default PM role does not include it).

## What the user fills out

### Enable Contract Admin & Procurement workflow

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Do you wish to use Workflow for Contract and Procurement Modules? | Yes | Yes/No | |
| Type of Workflow | Yes | Enum | Feature based (all projects; named approvers or Project Details alias); Feature based with Project Manager Alias or Admin Approvers (all projects); Project/Feature based (rules scoped to specific projects) |
| Notifications for actions | No | Checkboxes | Exact checkbox labels not listed on the enable page |
| AbandonWorkflow | Yes | Enum | Allow Admins or Next Approver (default); Allow Only Approvers; Allow All Users Who Have Feature Access |

**Constraint:** rules are company-wide **or** project-specific, not mixed.

### Create / edit a value rule

Official overview: add rules based on **value** (example: POs with total > $5,000); pick approvers who have feature access; multiple rules per feature (parallel vs sequential) — user is **prompted which rule applies**. Copy Feature Rule copies Module/Feature/Rule Name/Rule Description.

The dedicated “add one rule” field list (operator, amount, sequential vs parallel, approver grid columns) was not on the fetched create/copy pages. Confirmed persisted concepts:

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Module | Yes | Enum | Contract Administration or Procurement |
| Feature | Yes | Enum | COs, CPRs, Prime contracts, Prime invoices; Bills, POs, PO COs, Sub invoices, SCOs |
| Rule Name | Yes | Text | Editable in copy grid |
| Rule Description | No | Text | Editable in copy grid |
| Value threshold | Yes | Amount + comparison | “Greater than $5,000” is the official example; exact operator list not confirmed in help |
| Approvers | Yes (feature-based) | Users and/or aliases | Only users with feature access; alias = Project Details field |
| Parallel vs sequential logic | Yes if multiple approvers | Enum | Official: one rule parallel, another sequential |
| Destination Module/Feature | On copy | Enum | Copy Feature Rule wizard |

Do not invent fields such as “percent complete” or “cost code” as rule criteria — help states value only.

### Enable Time & Expenses workflow

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Enable T&E workflow | Yes | Toggle | Requires five or more licenses |
| Follow strict rules when adding time entries? | No | Checkbox | When on, employee dropdown = self + subordinates + Time Approval Access list |
| Specify managers | Yes for manager approve | Employee field | Org chart |
| Time Approval Access | No | User property | Indirect reports |

No value-threshold rules for timecards.

## What Sage CM saves

- Header record: workflow enablement + type + abandon policy (CA/P); T&E enable + strict flag.
- Line / child records: each CA/P rule (module, feature, name, description, value test, approver set, parallel/sequential, optional project scope).
- System-generated values: none until a transaction initiates a rule (instance + lock).
- Files / attachments: none.
- Audit / workflow fields: completed instances survive a type change; in-progress are abandoned.

## Statuses and lifecycle

Workflow off: users set Pending/Approved on the transaction. Workflow on: only Pending until the rule runs; status field disabled; Sage sets Approved / Not Approved from approver response. Listing colors: yellow pending, green approved, red not approved. Abandon → edit → reinitiate (preferred vs not-approved + recreate).

## Dates that drive alerts

No due date on the rule. Email alerts fire when a transaction matches and is submitted (Home Workflow tab). Transaction status dates still exist on the source document.

## Relationships

- Upstream: security roles, Project Details aliases, employee managers.
- Downstream: locked primes/COs/CPRs/invoices/POs/bills/subs; T&E approval; Home Workflow tab.
- Not used for: RFI/submittal Sequential-Parallel TeamLink (record-level).

## Reports and exports

No workflow-rules log report named in fetched help. Transaction listings show color-coded approval.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Amendable process definition | `workflow_definitions` (process_key, version, project_id, published) | implemented — different model |
| Steps / queues | `workflow_definition_steps`, `workflow_queues` | implemented |
| Live instance snapshot | `workflow_instances`, `workflow_instance_steps` | implemented |
| Value-threshold CA/P rules | none | none |
| T&E manager approval | HRMS leave/timesheet/expense `approver_user_id` | partial |
| Submittal workflow_instance_id | `submittals.workflow_instance_id` | partial |
| API | `backend/app/api/_workflow_service.py` | implemented |

## Sources

- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_Overview.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_Enable.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_ContractsProcurement_CreatingRules.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/Workflow/Workflow_TimeExpenses_Overview.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Global.htm
- Local: `backend/app/models/workflow.py`, `backend/app/api/_workflow_service.py`
