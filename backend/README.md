# USIS CM — Backend

Flask + SQLAlchemy 2.x + Alembic, talking to PostgreSQL 18.
This package owns the database schema and (eventually) the JSON APIs that the
W3CRM front-end will call.

## Layout

```
backend/
├── app/
│   ├── __init__.py        # Flask app factory
│   ├── config.py
│   ├── extensions.py      # db, migrate singletons
│   └── models/            # ORM models (one file per domain area)
├── migrations/
│   ├── env.py             # Alembic env, wired to Flask app
│   └── versions/
│       └── 0001_phase1_core.py
├── scripts/
│   ├── bootstrap_db.sql   # creates role + database (run once)
│   └── bootstrap_db.ps1   # PowerShell wrapper for the above
├── requirements.txt
├── .env.example
└── README.md
```

## Phase 1 — what this migration creates

| Table | Purpose |
|---|---|
| `roles`, `users`, `user_roles` | RBAC scaffolding |
| `companies`, `contacts` | GCs, owners, architects, subs, vendors + their people |
| `projects` | Central project entity (UUID PK; many FKs hang off this) |
| `documents` | Polymorphic base for every file the platform stores |
| `drawings` | Joined-table specialization of `documents` |
| `drawing_annotations` | Measurements + user notes + AI reviews |
| `audit_log` | Append-only compliance trail |

PostgreSQL native enums are used for `company_type`, `project_status`,
`project_type`, `document_type`, `annotation_type`, `annotation_severity`.

## One-time setup (Windows)

1. **PostgreSQL bin on PATH** — confirm `psql --version` works in a new
   PowerShell. If not, add `C:\Program Files\PostgreSQL\18\bin` to your
   PATH and reopen the terminal.

2. **Python venv + deps** (from `backend\`):

   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

3. **Environment file**:

   ```powershell
   Copy-Item .env.example .env
   # then edit .env and set POSTGRES_SUPERUSER_PASSWORD and USIS_APP_DB_PASSWORD.
   # Make sure DATABASE_URL embeds the same USIS_APP_DB_PASSWORD you choose.
   ```

4. **Create the role + database** (re-runnable; safe to repeat):

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\bootstrap_db.ps1
   ```

5. **Apply the schema**:

   ```powershell
   flask db upgrade
   ```

   You should see `0001_phase1_core` applied. Verify with:

   ```powershell
   $env:PGPASSWORD = (Get-Content .env | Select-String '^USIS_APP_DB_PASSWORD=').ToString().Split('=',2)[1]
   psql -U usis_app -h localhost -d usis_cm -c "\dt"
   Remove-Item Env:PGPASSWORD
   ```

   Expect 10 tables (`roles`, `users`, `user_roles`, `companies`, `contacts`,
   `projects`, `documents`, `drawings`, `drawing_annotations`, `audit_log`)
   plus Alembic's own `alembic_version`.

6. **Smoke-test Flask**:

   ```powershell
   flask run
   # then in another shell:
   curl http://127.0.0.1:5000/healthz
   ```

   **W3CRM / Gulp + API:** Static pages call ``http://127.0.0.1:5000/api/...``. The browser must see ``Access-Control-Allow-Origin`` matching the page origin (e.g. BrowserSync on ``http://localhost:3002``). In ``FLASK_ENV=development`` the app merges common localhost ports automatically; for LAN/Tailscale URLs set ``CORS_ORIGINS_EXTRA`` in ``.env``. Also avoid running **two** Flask processes on port 5000 (``netstat -ano | findstr :5000``) — Windows can leave both listening and you may hit an older instance without the right CORS rules.

## Production / staging checklist

1. Leave ``USIS_API_DEV_ALLOW_ANY`` unset or ``0`` so the API does not synthesize an admin user (``FLASK_ENV=development`` alone no longer enables that). For throwaway local hacking only, you may set ``USIS_API_DEV_ALLOW_ANY=1``.
2. Set a long random ``SECRET_KEY``; configure ``DATABASE_URL`` for your PostgreSQL host.
3. Set ``CORS_ORIGINS`` (and ``CORS_ORIGINS_EXTRA`` if needed) to the exact browser origins that host the W3CRM shell; credentialed ``fetch`` requires a match — see ``app/__init__.py``.
4. Point ``USIS_POST_LOGIN_REDIRECT`` at your deployed dashboard URL after ``/auth/login``.
5. Run ``flask db upgrade`` on deploy; back up the database and ``instance/`` upload folders (drawings, ``spec_section_uploads``, ``rfi_attachment_uploads``) on a schedule — see ``scripts/backup_usis_cm.ps1``.
6. Run ``scripts/smoke.ps1`` (or hit ``/healthz``) after each deploy. Responses include ``X-Request-Id`` for correlation in logs.
7. Build the Gulp ``dist`` with the correct API base for production (see ``gulp/src/elements/meta.html`` and ``window.USIS_API_BASE``).

- Edit a model under `app\models\` → generate a migration:

  ```powershell
  flask db migrate -m "describe the change"
  flask db upgrade
  ```

- Roll back the last migration:

  ```powershell
  flask db downgrade -1
  ```

- Inspect current revision:

  ```powershell
  flask db current
  ```

## Tests

Use the **backend virtualenv** (system Python often lacks ``psycopg`` or picks up an unrelated ``pytest-flask`` that breaks the ``app`` fixture).

From ``backend\``:

```powershell
.\.venv\Scripts\pip install -r requirements.txt
.\.venv\Scripts\pytest tests -v
```

From the **repository root** (``pyproject.toml`` wires ``pythonpath``); still call the venv’s Python:

```powershell
.\backend\.venv\Scripts\python -m pytest
```

Convenience wrapper:

```powershell
powershell -ExecutionPolicy Bypass -File backend\scripts\run_tests.ps1
```

## Reference-data imports (already in this repo)

Each of these has a migration AND a loader script under `scripts\`. Run the
migration first (`flask db upgrade`), then the loader.

| Migration | Table | Loader | Source CSV (default) |
|---|---|---|---|
| `0002_wage_rates` | `wage_rates` | `scripts\load_wage_rates.py` | `…\Database files\all_wage_rates.csv` |
| `0003_material_pricing` | `material_pricing` | `scripts\load_material_pricing.py` | `…\BOBRICK MATERIAL PRICING.CSV` (truncate) + `uPDATED PRICING.CSV` (upsert); use `--all-defaults` |
| `0004_sales_tax_rates` | `sales_tax_rates` | `scripts\load_sales_tax_rates.py` | `…\Database files\cdtfa_sales_use_tax_rates_raw.csv.csv` |
| `0005_lead_estimates` | `lead_estimates` | `scripts\load_lead_estimates.py` | `…\Database files\bc_projects_*.csv` |
| `0006_corecon_transactions` | `corecon_transactions` | `scripts\load_corecon_transactions.py` | `…\Database files\corecon_transactiondetailsapi_export*_by_TransactionSource_*.csv` (all 7 files) |
| `0007_link_jobs` | adds `project_id` FK to `lead_estimates` and `corecon_transactions` | `scripts\link_jobs.py` | (operates on already-loaded rows) |
| `0010_takeoff_line_items` | `takeoff_line_items` | (created via app / API) | Unified estimate lines per `lead_estimates` row |
| `0012_bc_oauth` | `buildingconnected_oauth_tokens` | OAuth callback + sync API | APS refresh/access for BuildingConnected |

Each loader takes `--csv <path>` to override the default and a mode flag
(`--truncate` / `--no-truncate`, or `--mode upsert|truncate` for the
BuildingConnected and Corecon imports). The Corecon loader auto-discovers
all seven `_by_TransactionSource_*` files in `--dir` (default: ``DATABASE_FILES_ROOT``
from ``.env``, else the OneDrive "Database files" folder; see ``scripts/db_csv_paths.py``)
and merges them into one table; `transaction_source`
is the discriminator column.

**One-shot orchestration (PowerShell, from ``backend/``):**

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_all_reference_imports.ps1
```

Runs reference loaders, BuildingConnected leads, Corecon, HubSpot contacts (if a CSV is present), then ``link_jobs.py``, then probes ``/healthz`` if Flask is listening on port 5000.

**HubSpot → ``companies`` / ``contacts``:**

```powershell
python scripts\load_hubspot_contacts.py
# or: python scripts\load_hubspot_contacts.py --csv "E:\path\to\export.csv"
```

Set ``HUBSPOT_CONTACTS_CSV`` or place ``hubspot-crm-exports-*.csv`` under ``DATABASE_FILES_ROOT``.

### BuildingConnected REST API (live sync)

1. In the [Autodesk Developer](https://aps.autodesk.com/) console, create an app, enable **BuildingConnected** API v2, and set the **Callback URL** to the same value as ``AUTODESK_OAUTH_REDIRECT_URI`` in ``.env`` (for local Flask, e.g. ``http://127.0.0.1:5000/api/v1/integrations/buildingconnected/oauth/callback``).
2. Copy ``AUTODESK_CLIENT_ID`` and ``AUTODESK_CLIENT_SECRET`` into ``.env`` (never commit them). Set scopes in ``AUTODESK_OAUTH_SCOPES`` to match the app (read-only sync typically uses ``data:read`` if that is what your app registration lists).
3. Apply migration ``0012_bc_oauth`` (``flask db upgrade``), then start Flask and open ``/api/v1/integrations/buildingconnected/oauth/start`` in a browser while logged into Autodesk as the BC user whose data you want to sync.
4. After a successful callback, call ``GET`` or ``POST`` ``/api/v1/integrations/buildingconnected/sync`` with ``BUILDINGCONNECTED_SYNC_ENABLED=1`` (defaults on in ``FLASK_ENV=development``). Projects are upserted into ``lead_estimates`` using the same column mapping as the ``bc_projects`` CSV import.

### Textura Payment Management (pull sync)

1. Apply migration ``0041_textura_external_ids`` (``flask db upgrade``).
2. Set ``TEXTURA_API_BASE`` (production or test tenant), ``TEXTURA_USERNAME``, and ``TEXTURA_PASSWORD`` in ``.env``, **or** save credentials via ``PUT /api/v1/integrations/textura/credentials`` (encrypted with ``TOKEN_ENCRYPTION_KEY``).
3. Enable sync: ``TEXTURA_SYNC_ENABLED=1`` (defaults on in ``FLASK_ENV=development``).
4. Match Textura jobs to USIS projects by ``projects.textura_project_id``, ``projects.number`` (Textura ``MainJobNumber``), or project name. Set ``TEXTURA_AUTO_CREATE_PROJECTS=1`` to create stub projects from Textura owner projects.
5. **Global sync:** ``POST /api/v1/integrations/textura/sync`` — pulls owner projects and invoice export into ``projects`` and ``pay_applications``.
6. **Per-project sync:** ``POST /api/v1/projects/<id>/integrations/textura/sync`` — same pull, scoped to one project (also available on the project **Invoicing** tab as **Sync from Textura**).

See ``Plan/28_textura_integration_plan.md`` for Phase 2 (push subcontracts) and later phases.

### Shared job UID

After migration `0007_link_jobs`, both `lead_estimates` and `corecon_transactions`
have a nullable `project_id UUID` column pointing at `projects.id`. That gives
every job a single stable UID across pre-award (BuildingConnected) and post-award
(Corecon) data.

To populate the link after a load:

```powershell
flask db upgrade
python scripts\link_jobs.py
# optional: also try to match BC leads to projects by exact name
python scripts\link_jobs.py --match-leads
# preview without committing
python scripts\link_jobs.py --dry-run
```

What `link_jobs.py` does:

1. Reads every distinct `project_number` from `corecon_transactions`, upserts a
   row into `projects` keyed by `projects.number` (so Corecon's job number drives
   the project registry).
2. Updates `corecon_transactions.project_id` by joining
   `projects.number = corecon_transactions.project_number`.
3. With `--match-leads`, conservatively links `lead_estimates` to a project
   when the BC `name` matches a `projects.name` exactly (case-insensitive).
   Anything fuzzier is left for manual curation since BC's naming
   (e.g. `Wheeler Hangar PN76898`) does not generally match Corecon's
   internal project numbers (e.g. `23090`).

Re-running the script is safe; it is fully idempotent.

## Roadmap (still to come — Plan 1–13 application schemas)

| Phase | Migration | Module |
|---|---|---|
| 7 | `0007_crm_bids` | `bid_opportunities`, `lead_contacts` |
| 8 | `0008_takeoff` | `takeoff_line_items`, `job_cost_codes`, `cost_library` |
| 9 | `0009_estimating` | `estimates`, `estimate_line_items` |
| 10 | `0010_rfp` | `rfps`, `rfp_line_items`, `rfp_responses` |
| 11 | `0011_pm_field` | `tasks`, `task_dependencies`, `daily_logs`, `punch_list_items`, `field_photos`, `timesheets` |
| 12 | `0012_safety` | `safety_policies`, `training_records`, `daily_safety_logs`, `safety_observations`, `incidents`, `jhas`, `corrective_actions` |
| 13 | `0013_financials` | `budgets`, `budget_line_items`, `commitments`, `commitment_line_items`, `change_orders`, `invoices`, `payments`, `financial_transactions` |
| 14 | `0014_ai` | `ai_chat_sessions`, `ai_chat_messages` |
| 15 | `0015_cross_cutting` | `notifications`, `sync_queue`, `attachments` |

Each phase is one Alembic revision and can be applied independently.
