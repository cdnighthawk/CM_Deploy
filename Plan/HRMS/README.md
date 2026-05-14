# USIS HR Management System (HRMS)

## Stack (this repository)

This HRMS is implemented **inside USIS_CM** as:

- **Backend:** Flask + SQLAlchemy + PostgreSQL (Alembic migrations), REST under `/api/v1/hrms/…`
- **Frontend:** Existing W3CRM / `usis-*.html` shell (mobile-responsive Bootstrap), same auth as the app (`/auth/login`, session cookie, `X-Usis-User-Id` in dev)

It is **not** a WordPress plugin. If you need WordPress + ACF + CPT instead, say so and we can mirror this schema as a plugin or sync via API.

## Goals (Sage HR–style, no recruitment)

Full feature list lives in the product brief; implementation is **modular** (enable/disable via `hrms_module_settings` and future admin UI).

## Repository layout

| Path | Purpose |
|------|---------|
| `Plan/HRMS/README.md` | This file — architecture and roadmap |
| `backend/migrations/versions/0030_hrms_foundation.py` | Core + leave + timesheet + shift + goals + reviews + expenses + GDPR + audit tables |
| `backend/app/models/hrms_core.py` | SQLAlchemy models for HRMS tables |
| `backend/app/hrms/` | Blueprint, services, permission helpers |
| `backend/scripts/seed_hrms_sample.py` | Optional sample leave types + module flags (run manually) |
| `W3CRM-…/gulp/src/usis-hrms-home.html` | Starter dashboard (cards + API hook) |

## Roles (multi-role)

Use existing `roles` / `user_roles` plus new role codes (assign in **User admin** or seed script):

- **`hr_admin`** — Super Admin (HR): full org, settings, exports, GDPR tools
- **`hr_manager`** — Managers: team approvals, team calendar, reports
- **`hr_employee`** — Employees: self-service (explicit flag; any authenticated user can hit “self” endpoints where noted)

`is_superuser` continues to imply full access.

## Security & compliance (phased)

| Topic | Phase 1 (now) | Later |
|-------|----------------|-------|
| Auth | Same as CMS app: Flask session + `current_user` / headers | SSO / OIDC optional |
| Sensitive fields | Columns reserved; store non-sensitive data only | Fernet / vault column encryption |
| Audit | `hrms_audit_logs` table + service helper | Wire every mutation |
| GDPR | `hrms_gdpr_consents` + export/delete stubs in API | Full DSAR automation |
| Email / in-app | `hrms_notifications` rows | Celery + SMTP / push |

## Questions for you (when ready)

1. Confirm **no WordPress** for this deployment, or specify WP + sync strategy.
2. Approximate **employee count** and **single legal entity vs multi-company**.
3. **Leave accrual rules** (by tenure, by pay type, carryover caps).
4. **Brand colors** (hex) for a dedicated HRMS theme or reuse W3CRM primary.
5. **Clock-in** constraints: GPS required? IP allowlist? kiosk mode?

## Next modules (build order)

1. Employee profiles + org chart + directory (CRUD + UI)
2. Leave balances + requests + approvals + calendar
3. Timesheets + approvals + reports
4. Shifts + swaps + notifications
5. Performance (goals + cycles + templates)
6. Expenses + multi-currency
7. Dashboards + CSV/PDF exports + admin settings UI
