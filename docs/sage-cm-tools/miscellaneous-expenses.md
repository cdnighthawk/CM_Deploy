# Miscellaneous expenses

Status: complete
Sage CM module: Time and Expenses
Official help: https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/MiscExpenses/MiscExpensesOverview.htm

## Purpose

Employee miscellaneous expenses record project costs when a PO or subcontract is not practical (fuel on a company card, reimbursable meals, hotel, per diem). Payment Type is required and drives AccountingLink export (credit card purchase vs check, GL mapping). Approved expenses appear in Committed Cost and Cost To Date and can import to Cost Plus prime invoices when Billable.

## Where it lives

- Time & Expenses module → Timecard and Expense Stats → Misc. Expenses → Add Misc. Expenses or Import From Excel.
- Project Home → Time & Expenses → Misc. Expenses → Actions → Add Misc. Expenses.
- Record form with header (project, prime, payee) plus an Expenses line grid.
- Mobile: field users can enter expenses on the mobile apps (same T&E security). TeamLink does not enter misc expenses.

## Who uses it

- Entry: roles with Employee miscellaneous expenses (entry only), including Time & Expense Field User.
- Approve / set Status to Approved on the form: Administrator or Financial Administrator.
- AccountingLink export: financial admin after Approved.

## Prerequisites

- Payment types in Feature Settings → Time & Expenses (Cash, Check, Credit Card – Amex, etc.). Required.
- Optional: Misc. Expense Types (Gas, Food, Lodging); tax codes.
- Company in the project directory; employee selected as Expense Contact.
- Approved prime contract with Status Date; job cost codes.
- Credit-card companies exist as Contact Management companies when Payee Type is vendor/card.

## What the user fills out

### Header (Add Misc. Expenses)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Project | Yes | Lookup | |
| Prime Contract | Yes | Lookup | Approved |
| CO # | No | Lookup | Must exist if set |
| WO # | No | Lookup | |
| Company | Yes | Lookup | Your firm / expense company; prefilled, editable |
| Expense Contact | Yes | Lookup | Employee (help: ensure an employee is selected) |
| Payment Type | Yes | Lookup | Feature Settings list; drives AccountingLink |
| Payee / Payee Type | Yes | Enum + lookup | Import: Employee or Payee Company. Add form: if Payee Type is Vendor, Payee Company is required (e.g. Amex) |
| Status / Status Date | Admin only | Enum + date | Admins/Financial Admins may set Approved and Status Date on create |

### Expense lines

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Date | Yes | Date | Expense / transaction date (analytics filter) |
| Expense Type | No | Lookup | Gas, Food, Lodging, etc. |
| Description | Yes | Text | ItemDescription on import |
| Quantity | Yes on import; optional on add (defaults allowed) | Number | Import: cannot be blank or zero |
| Unit | No | Text | ≤ 10 chars (Ea, LS) |
| Unit Price | Import yes; add optional | Number | Line amount = qty × unit price when both set |
| Cost Code | Yes | Lookup | Job cost code |
| Tax code | No | Lookup | Must exist if set |
| Resource | No | Enum | M, L, E, S, O. Default O (Other) |
| Billable status | Cost Plus | Enum | Billable / Unbillable / On Hold. Ignore on FLS and Unit Price contracts |

### Excel import columns (authoritative)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| ProjectNumber | Yes | Text | Must exist |
| PrimeContractNumber | Yes | Text | Must exist |
| ChangeOrderNumber | No | Text | Must exist if set |
| ExpenseDate | Yes | Date | DD-MMM-YYYY, MM-DD-YYYY, or YYYY-MM-DD |
| ExpenseType | No | Text | Must match Feature Settings |
| PaymentType | Yes | Text | Must match Feature Settings |
| EmployeeName | Yes | Text | Employee display name |
| PayeeType | Yes | Text | Employee or Payee Company |
| PayeeCompany | Conditional | Text | Required if Payee Company; must exist in Contact Management |
| ItemDescription | Yes | Text | |
| ItemUnit | No | Text | ≤ 10 characters |
| ItemQuantity | Yes | Number | Not blank or zero |
| ItemUnitPrice | Yes | Number | |
| ItemResource | Yes | Text | M, L, E, S, O (default O if omitted) |
| ItemCostCode | Yes | Text | Must exist |
| ItemTaxCode | No | Text | Must exist if set |
| BillableStatus | Yes | Text | Billable, Unbillable, or On Hold |

## What Sage CM saves

- Header record: miscellaneous expense (project, prime, optional CO/WO, company, expense contact, payment type, payee type/company, status, status date).
- Line / child records: expense lines (date, type, description, qty, unit, unit price, JCC, tax, resource, billable).
- System-generated values: line and header totals; tax per tax-code logic (separate help topic); default Resource O.
- Files / attachments: receipts are typical practice; official add/import pages do not list a receipt field. Linked Files on the record after save is the usual Sage pattern — not confirmed on the add form itself.
- Audit / workflow fields: Draft → Pending Submission → Pending → Not Approved → Approved; exported/locked when Global Settings auto-lock after AccountingLink.

## Statuses and lifecycle

Official sequence: Draft → Pending Submission → Pending → Not Approved → Approved. Only Approved export via AccountingLink and hit analytics. Billable + Approved can import to Cost Plus prime invoices. Negative totals have special QBO export behavior (AccountingLink AP prefs).

Use Bills (no PO) instead when many materials need different JCCs or when paying an employee by bill/check for hardware-store runs — see official transaction examples.

## Dates that drive alerts

Expense Date / Transaction Date (analytics). Status Date when approved. No correspondence-style due date. Payment-type export rules fire at AccountingLink sync, not an alert calendar.

## Relationships

- Upstream: payment types, expense types, tax codes, employee, payee company, approved prime, JCC, optional CO/WO.
- Downstream: project analytics; Cost Plus prime invoices; AccountingLink (export as credit card purchase or check purchase per payment type); optional lock.
- Sibling: Bills — use bills when line-level AP/vendor documents are needed.

## Reports and exports

- Standard log report: Employee miscellaneous expenses.
- AccountingLink AP: Misc. Expense Payment Type Linking Preferences.
- Bulk update and approve functions on the misc expense list.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Expense report header | `hrms_expense_reports` (`title`, `currency`, `status`, submitted/approved/exported/reimbursed) | partial |
| Expense lines | `hrms_expense_lines` (project, spent_at, amount, category, merchant, description, receipt_document_id) | partial |
| Payment Type / Payee Company / Resource / JCC / tax | none on HRMS lines | none |
| Billable / CO / WO / prime | none | none |
| Receipt file | `receipt_document_id` → `documents` | implemented on HRMS |
| HRMS expense UI | `usis-hrms-expenses.html`; `backend/app/hrms/_expense_service.py` | partial |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/MiscExpenses/MiscExpensesOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/MiscExpenses/MiscExpensesAddManual.htm
- https://help.sagecm.intacct.com/Content/Modules/Import/ImportMiscExpenses.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/FeatureSettings/FeatureSettings_TimeExpenses_MiscExpensePaymentTypes.htm
- https://help.sagecm.intacct.com/Content/Modules/Procurement/Bills/ExampleBillMiscExpenses.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/MiscExpenses/CreditCardSetup.htm
- Local: `backend/app/models/hrms_core.py`, `backend/app/hrms/_expense_service.py`
