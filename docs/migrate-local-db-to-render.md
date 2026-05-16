# Migrate local PostgreSQL to Render (USIS CM)

Copy **data** from your Windows dev database into the Render Postgres instance that already has the **schema** from `flask db upgrade` (Blueprint `preDeployCommand`).

**Does not migrate:** files under `backend/instance/` (drawings, spec PDFs, RFI attachments). See [Upload instance files](#upload-instance-files-optional) below.

## Prerequisites

| Requirement | Notes |
|-------------|--------|
| PostgreSQL client tools | `pg_dump`, `pg_restore`, `psql` on PATH (e.g. `C:\Program Files\PostgreSQL\18\bin`) |
| Local DB populated | `backend/.env` with working `DATABASE_URL` |
| Render deployed once | `usis-cm-db` exists; web service ran `flask db upgrade` |
| External DB URL | Render Dashboard → **usis-cm-db** → **Connect** → **External Database URL** |

## Environment variables (shell only — do not commit)

```powershell
cd E:\programs\USIS_CM\backend

# Optional: override local source (default = DATABASE_URL from .env)
$env:LOCAL_DATABASE_URL = "postgresql+psycopg://usis_app:YOUR_LOCAL_PW@127.0.0.1:5432/usis_cm"

# Required: paste External connection string from Render (postgres:// or postgresql://)
$env:RENDER_DATABASE_URL = "postgresql://usis_app:...@dpg-....render.com/usis_cm"

# Optional: backup output folder (default: repo backups/)
$env:USIS_BACKUP_DIR = "E:\programs\USIS_CM\backups"
```

The script normalizes `postgresql+psycopg://` and `postgres://` to `postgresql://` for libpq tools.

## Recommended procedure

### 1. Test connectivity

```powershell
powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1 -ConnectivityOnly
```

Confirms both databases are reachable and prints `alembic_version` on each. Versions should match (same migration head on local and Render).

### 2. Push data (backs up Render first)

```powershell
powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1
```

What it does:

1. **Backup Render** → `backups/render_usis_cm_before_push_YYYYMMDD_HHMMSS.dump` (custom format, full DB)
2. **Dump local data only** → `backups/local_usis_cm_data_only_YYYYMMDD_HHMMSS.dump`
3. **Restore** into Render with `pg_restore --data-only --disable-triggers --no-owner --no-acl`

Assumes Render tables are **empty** after migrations. If you already created a bootstrap admin or a prior restore left rows:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1 -TruncateRenderBeforeRestore
```

**Warning:** `-TruncateRenderBeforeRestore` deletes **all** rows in `public` tables on Render before restore.

### 3. Align encryption keys on Render

| Data | Key on Render |
|------|----------------|
| Login passwords (`users.password_hash`) | No action — werkzeug hashes are self-contained |
| I-9 Section 1, W-4, BuildingConnected refresh tokens | Set **`TOKEN_ENCRYPTION_KEY`** on Render to the **same** value as local `.env` |
| Fallback when `TOKEN_ENCRYPTION_KEY` is unset | Uses **`SECRET_KEY`** — must match local if you relied on the dev fallback |

Render Blueprint auto-generates new `SECRET_KEY` and `TOKEN_ENCRYPTION_KEY`. If local HR or integration data was encrypted, **copy your local values** into Render Dashboard → **usis-cm** → Environment before testing those features.

Do **not** rotate `TOKEN_ENCRYPTION_KEY` after encrypted data exists ([render-deploy.md](render-deploy.md) troubleshooting).

### 4. Verify login

Open `https://<your-service>.onrender.com/page-login.html` and sign in with a **local** user email/password from the restored `users` table.

### 5. Smoke test

```powershell
# Against production URL (edit smoke.ps1 base URL if needed)
powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1
```

Or hit `GET /healthz` in the browser.

## Upload instance files (optional)

Binary uploads are **not** in PostgreSQL. They live under `backend/instance/` locally and on Render’s persistent disk (`render.yaml` → `backend/instance`).

| Local path | Typical contents |
|------------|------------------|
| `instance/drawing_uploads/` | Drawing files |
| `instance/spec_section_uploads/` | Spec PDFs |
| `instance/rfi_attachment_uploads/` | RFI attachments |

To copy to production:

1. Render Dashboard → **usis-cm** → **Shell** (root `backend/`)
2. Use `scp`, Render disk snapshot, or a one-off archive upload — there is no built-in sync script yet.
3. Paths must match what the app expects (defaults under `instance/` unless env overrides in `.env.example`).

DB rows may reference filenames/paths; without copying files, uploads will 404 or show missing attachments.

## Rollback

If restore went wrong, restore the Render backup from step 2:

```powershell
$env:RENDER_DATABASE_URL = "postgresql://..."   # same External URL
pg_restore --dbname=$env:RENDER_DATABASE_URL --clean --if-exists --no-owner --no-acl backups\render_usis_cm_before_push_YYYYMMDD_HHMMSS.dump
```

Or use Render’s point-in-time backup (paid plans) from the database dashboard.

## Manual alternative (no script)

```powershell
# Backup Render
pg_dump --dbname=$env:RENDER_DATABASE_URL -Fc -f render_backup.dump

# Local data only
pg_dump --dbname=$env:LOCAL_DATABASE_URL --data-only -Fc -f local_data.dump

# Restore (empty target tables)
pg_restore --dbname=$env:RENDER_DATABASE_URL --data-only --disable-triggers --no-owner --no-acl local_data.dump
```

Use `postgresql://` URIs (strip `+psycopg` from SQLAlchemy URLs).

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `alembic_version` missing on Render | Deploy did not run `flask db upgrade` — fix deploy, then re-run push |
| Version mismatch local vs Render | Run `flask db upgrade` locally or redeploy Render before push |
| Duplicate key / pg_restore errors | Render not empty — use `-TruncateRenderBeforeRestore` |
| Login works locally but not on Render | Wrong site URL / cookies — use production URL; check `SESSION_COOKIE_SECURE` |
| I-9 / W-4 decrypt errors | `TOKEN_ENCRYPTION_KEY` (or `SECRET_KEY` fallback) differs from local |
| SSL connection errors to Render | External URL requires SSL; use the URL Render provides unchanged |

## Related docs

- [render-deploy.md](render-deploy.md) — Blueprint, secrets, first deploy
- [backend/RUNBOOK.md](../backend/RUNBOOK.md) — backups, uploads, smoke test
