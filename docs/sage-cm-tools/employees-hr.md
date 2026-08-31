# Employees (HR / Time & Expenses)

Status: complete
Sage CM module: Time and Expenses / Contact Management
Official help: https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/Employees/EmployeesOverview.htm

## Purpose

The employee record is the HR/payroll contact used for labor timecards, miscellaneous expenses, clock in/out, org chart/managers, and (when licensed) a Standard or Time/Expense user login. Sage’s Time & Expenses employee form is richer than a plain Contact Management contact (education, licenses, payroll rate tables). Sage is not a full I-9/W-4 hire-wizard HRIS; those USIS objects have no Sage equivalent.

## Where it lives

- Time & Expenses → Employee and Labor Stats → Active Employees → Add Manually, or open the employee name → Edit.
- Contact Management can also create the person as a company contact; T&E is recommended for payroll.
- Settings → Company Settings → Users can create a user and a new employee together.
- Organization: specify managers; display org chart.
- Mobile: field users do not administer employee payroll. TeamLink users are external and are not this record.

## Who uses it

Only Administrator, Financial Administrator, or a custom role with Employees and payroll setup can review/edit T&E employee data. Other roles use the employee as a lookup on timecards and expenses.

## Prerequisites

- Your firm (company) exists.
- Optional Feature Settings: Contact Management titles; T&E employee departments, payroll items, payroll burden templates, workers comp codes.
- AccountingLink if importing employees from Intacct, Sage 100/300, QuickBooks, or Xero.

## What the user fills out

### Details tab — General

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company | Yes | Lookup | Defaults to your firm; changeable |
| Salutation | No | Lookup | Feature Settings titles |
| First Name | Yes | Text | |
| Middle Name | No | Text | |
| Last Name | Yes | Text | |
| Suffix | No | Text | |
| Display Name | Yes | Text | Default First + Last; used as EmployeeName on imports and often as User login |
| Title | No | Lookup | |
| Is Active | Yes | Checkbox | Clear to inactivate (stops new T&E use) |
| Track Time & Expenses | Conditional | Checkbox | Required if the person will have labor cards or misc expenses |

### Business Contact Info

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Email | Yes | Email | Business email |
| Business address, phone, fax | No | Address | Use when work address differs from company address |

### Home Contact Info

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Home address / phone | No | Address | Optional |

### Organization Info

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Employee Id | Recommended | Text | |
| Gov. Id | Recommended | Text | Government ID |
| Gender | Recommended | Lookup | |
| Department | No | Lookup | Feature Settings employee departments — list exists; field placement on form not separately listed beyond “additional information” |
| Additional org fields | No | Mixed | Help: “Enter any additional information as needed” — exact remaining org labels not confirmed in help |

### Emergency Contact

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Emergency contact person fields | No | Text | Official help does not enumerate subfields (name/phone/etc.) |

### Comments tab

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Comments | No | Text | |

### Timecard Rates tab — Standard Payroll Rates

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Payroll Item | Yes | Lookup | From Feature Settings |
| Effective Date | No | Date | Optional Set Effective Date on multi-employee add |
| Base Rate | Yes | Money | Cost rate |
| Burden Rate | Yes* | Money | Enter or import payroll burden template; after template import, manual edit only if templates removed |
| Bill Rate | Yes | Money | Cost Plus only for billing |

### Project-specific payroll rates

Same payroll item + rates scoped to a project (status follows project active/inactive). Multi-employee Actions → Add Manually from Payroll Stats.

### Manager / org chart

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Manager | No | Lookup | Required for T&E workflow subordinate approval |

Education, licenses, and other child tables are mentioned on the overview (“additional fields and tables, such as education, licenses, and payroll rates”) but individual education/license columns were not confirmed in help.

## What Sage CM saves

- Header record: employee (contact + org + T&E flags), also visible as an active contact under the company.
- Line / child records: standard payroll rates; project-specific payroll rates; manager link; optional education/licenses (unverified columns); user login if Is User.
- System-generated values: display name default; inbound email when the employee is a user (generated, not editable); payroll rate active/inactive from archived payroll item or project status.
- Files / attachments: not listed on add/update profile help.
- Audit / workflow fields: Is Active; Track Time & Expenses; user lock/unlock lives on Users.

## Statuses and lifecycle

Active ↔ Inactive. Inactivate rather than delete when referenced on timecards. User license is separate (Standard vs Time/Expense user). Payroll items archived in Feature Settings inactivate standard rates.

## Dates that drive alerts

Effective Date on rates. Hire/term dates are not on the official add form (USIS HRMS has hire_date / termination_date). Insurance/license expiration alerts are company-level, not this employee form.

## Relationships

- Upstream: company, departments, payroll items, burden templates, titles.
- Downstream: labor timecards, clock in/out, misc expenses (Expense Contact), T&E workflow (manager), Users (login), AccountingLink employee sync.

## Reports and exports

Employee lists from Active Employees count; org chart; import/export payroll rates via Excel; AccountingLink employee import.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| Employee identity | `users` (email, first/last, phone, is_active) | partial |
| HR profile | `hrms_employee_profiles` (org_unit, manager, job_title, hire/term, employment_status) | partial |
| Pay scales | `hr_employee_pay_scales` | partial |
| Prevailing wage reference | `wage_rates` | implemented (not Sage payroll items) |
| Org units | `hrms_org_units` | partial |
| Hire wizard I-9/W-4/union | `hr_hire_applications` + document file tables | implemented — Sage-only |
| Dispatch / project pay revision | `hr_employee_dispatches` | implemented — Sage-only |
| Onboarding / policy / training | `hr_onboarding_items`, `hr_policy_acknowledgments`, `hr_training_assignments` | implemented — Sage-only |
| HR pages | `usis-hr-employee.html`, `usis-hr-dashboard.html`, `GET /api/v1/hr/employees/<id>` | implemented |
| Sage education/licenses tables | none | none |

## Sources

- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/Employees/EmployeesOverview.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/Employees/Employees_AddUpdateProfile.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/Employees/PayrollRateSetup_IndividualEmployee.htm
- https://help.sagecm.intacct.com/Content/Modules/HRLbrTimecardsMiscExp/Employees/PayrollRateSetup_MultipleEmployees.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Users_AddingLogins_Settings.htm
- Local: `backend/app/models/auth.py`, `backend/app/models/hr.py`, `backend/app/models/hrms_core.py`, `backend/app/models/hr_dispatch.py`, `backend/app/api/_hr_dashboard.py`
