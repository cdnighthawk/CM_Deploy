# Users and security roles

Status: complete
Sage CM module: Administration / Company Settings
Official help: https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Users_Overview.htm

## Purpose

Users are employees (or Time/Expense field users) who receive a login. Security roles are feature trees that grant Yes / Read only / Assigned tasks only / blank (no access). TeamLink users are unlimited external portal accounts configured per project, not Standard licenses. Administrators create users, assign roles, scope projects and files, set MFA/SSO, and copy default roles into custom roles.

## Where it lives

- Settings (gear) → Company Settings → Users (Standard Users and Time & Expense Users sections).
- Settings → Company Settings → Security (password policy, MFA, role list).
- Settings home shows current username + role; Change Password.
- TeamLink users: per project (not this Users grid).
- Mobile apps use the same Standard/T&E login; MFA applies to browser and mobile.

## Who uses it

Only Administrators add/lock/remove users and edit roles. Every user can change their own password. Non-admins may have Other preferences (Add/Edit Companies, Contacts, Change Project Status, Add/Edit Templates) if granted on their user record.

## Prerequisites

- Employee record (or create employee + user together).
- Purchased Standard or Time/Expense licenses (license count on Settings home).
- Unique business email and User Login (duplicate email disables MFA).
- Password policy configured before reset emails.

## What the user fills out

### Add user from existing employee

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Add new user from existing employee | Yes (path) | Option | |
| Employee | Yes | Lookup | Must already exist |
| Business Email | Yes | Email | |
| User Login | Yes | Text | Username |
| Security Role | Yes for Standard | Lookup | Not used for Time/Expense (fixed field-user role) |
| Send Email | Yes | Action | Credentials email |

### Add user and new employee

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| First / Last Name | Yes | Text | |
| Display Name | Yes | Text | Default First Last |
| Business Email | Yes | Email | |
| User Login | Yes | Text | |
| Security Role | Yes for Standard | Lookup | |
| Send Email | Yes | Action | |

### User properties — company/employee

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Company name | System | Text | Not editable here |
| Inbound email | System | Email | Generated; replies land in that user’s Email module |
| Salutation, first, middle, last, suffix, display name, title | Mixed | Text | |
| Mobile phone, business email | No / Yes | | |
| Active | Yes | Checkbox | |
| Is User | Yes | Checkbox | Clear to remove from users (employee remains) |

### User information

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| User login | Yes | Text | Default display name |
| Role | Yes (Standard) | Lookup | Default or custom |
| Hint question / Hint answer | No | Text | |
| Password | Policy | Secret | Change Password (self) or Reset password (email) |
| Access All Projects / Leads | No | Checkbox | Clear then pick allowed projects/leads |
| Access All Uploaded Files | No | Checkbox | Clear to restrict files |
| Time Approval Access | No | Lookup | Magnifying glass — indirect reports for T&E approval |

### Other preferences (Standard)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Receive notification for inbound emails | No | Checkbox | |
| Set Favorite Features / Push Notifications / Alerts | Admin | Actions | Administrator-only helpers |
| Add / Edit Companies, Contacts, Change Project Status, Add / Edit Templates | Non-admin | Checkboxes | Extra rights beyond the role tree |

### Session / locale / external login

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Timeout | Yes | Dropdown | Session duration; logout warning |
| Locale | Yes | Enum | English (United States) default; English (United Kingdom) changes currency/terminology |
| SSO / MFA | No | Config | Login with external provider |

### Security settings (company)

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Password policy | Yes | Enum | None; min 8; min 8 + numeral; min 8 + numeral + symbol |
| Sage CM MFA | No | Toggle + start date | Email security code; Trust this device 15 days |
| TeamLink portal MFA | No | Toggle + start date | Auth method 2 externals |
| Duplicate email check | System | | MFA disabled if duplicate emails |

### Custom security role

| Field | Required | Type | Notes / allowed values |
|---|---|---|---|
| Copy From | Yes | Lookup | A default role |
| Role Name | Yes | Text | |
| Feature checkboxes | Yes | Tree | Clear features this role cannot access |

Default roles (cannot edit; copy to customize): Administrator, Estimator, Estimating / Project Manager, Project Manager, Superintendent, Financial Administrator, Time & Expense Field User. Feature matrix is on the official default-roles page (Contact Management through File management). Notable T&E rows: Field User has entry-only labor/equipment/misc expense and photos/daily logs; no hours overview; no employees/payroll; no correspondence; schedules = assigned tasks only.

### User types (official)

| Type | Who | Access |
|---|---|---|
| Standard User | Internal employee | Role-based Sage CM |
| Time/Expense User | Internal employee | Field user role; special monthly pricing; cannot be modified |
| TeamLink User | External | TeamLink Portal; free; unlimited; per project |

## What Sage CM saves

- Header record: user login tied to employee/contact; role; project/file ACL; preferences; timeout; locale; SSO/MFA flags.
- Line / child records: custom role feature tree; Time Approval Access list; allowed projects/leads.
- System-generated values: inbound email; Company ID (org) is company-level; usage data views.
- Files / attachments: none on the user form.
- Audit / workflow fields: lock/unlock; last login/usage (usage data page); password reset emails.

## Statuses and lifecycle

Active user ↔ locked ↔ Is User cleared. License consumed while the person is a user. TeamLink is separate and unlimited.

## Dates that drive alerts

MFA start date. User-level Set Alerts chooses which feature dates appear (see alerts calendar). Session timeout is not an alert.

## Relationships

- Upstream: employee, licenses, password policy.
- Downstream: every module ACL; T&E approval (role + Time Approval Access + manager); TeamLink is project-level.

## Reports and exports

View Sage Construction Management usage data (official manage-users list). No “user log report” name confirmed in help.

## USIS / CM_Deploy mapping

| Sage concept | USIS table / API / page | Status |
|---|---|---|
| User | `users` | implemented |
| Roles | `roles`, `user_roles` | implemented |
| Module ACL | `role_module_permissions` + `backend/app/permissions/modules.py` | partial — USIS modules ≠ Sage feature tree |
| Superuser | `users.is_superuser` | implemented |
| Project membership | `ProjectMember` | partial vs Access All Projects |
| Mobile tokens | `mobile_refresh_tokens` | implemented |
| Password reset | `PasswordResetToken` | implemented |
| Time/Expense license type | none | none |
| TeamLink users | none | none |
| Admin UI | `user.html`; `_admin_users_service.py` | partial |

## Sources

- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Users_Overview.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Users_AddingLogins_Settings.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Users_Properties.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_Security.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_SecurityRoles_Default.htm
- https://help.sagecm.intacct.com/Content/Administration/Settings/CompanySettings/CompanySettings_SecurityRoles_Custom.htm
- Local: `backend/app/models/auth.py`, `backend/app/permissions/modules.py`, `backend/app/api/_admin_users_service.py`
