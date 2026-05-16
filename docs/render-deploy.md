# Deploy USIS CM to Render

Single HTTPS web service: Gulp-built UI + Flask API + PostgreSQL. Session cookies require one origin (no separate static host).

## Prerequisites

- GitHub repo with this codebase
- [Render](https://render.com) account

## 1. Apply the Blueprint

1. Render Dashboard → **New** → **Blueprint**
2. Connect the GitHub repository
3. Render reads [`render.yaml`](../render.yaml) at the repo root and creates:
   - PostgreSQL `usis-cm-db`
   - Web service `usis-cm` (Python 3.12)
   - Persistent disk on `backend/instance` (uploads; optional if using B2 — see [backblaze-b2.md](backblaze-b2.md))

## 2. Secrets (Dashboard → usis-cm → Environment)

`render.yaml` auto-generates `SECRET_KEY` and `TOKEN_ENCRYPTION_KEY`. Add:

| Variable | Purpose |
|----------|---------|
| `BOOTSTRAP_ADMIN_EMAIL` | First staff login email |
| `BOOTSTRAP_ADMIN_PASSWORD` | Temporary password (rotate after first login) |

Optional overrides:

| Variable | Default on Render |
|----------|---------------------|
| `USIS_ALLOW_SELF_REGISTER` | `1` (applicants can register on `/apply.html`) |
| `CORS_ORIGINS` | Auto from `RENDER_EXTERNAL_URL` if unset |
| `USIS_POST_LOGIN_REDIRECT` | `{RENDER_EXTERNAL_URL}/usis-dashboard.html` if unset |

### Object storage (Backblaze B2, recommended for production uploads)

Set all four variables to store drawings, spec PDFs, RFI attachments, and HR document photos in B2 instead of the Render disk. Full setup: [backblaze-b2.md](backblaze-b2.md).

| Variable | Purpose |
|----------|---------|
| `B2_APPLICATION_KEY_ID` | B2 application key ID |
| `B2_APPLICATION_KEY` | B2 application key secret |
| `B2_BUCKET_NAME` | Private bucket name |
| `B2_ENDPOINT` | S3-compatible endpoint (region-specific) |
| `B2_PREFIX` | Optional key prefix (e.g. `prod/usis-cm`) |

## 3. First deploy

- **Build**: `npm ci` + `gulp build` in `W3CRM-v3.0-13_September_2025/gulp`, then `pip install`
- **Release**: `flask db upgrade` (migrations through `0039`)
- **Start**: `gunicorn wsgi:app`

Watch logs for `Serving W3CRM static shell from .../gulp/dist` and `flask db upgrade` success.

## 4. Migrate local database (optional)

If you already have data in local PostgreSQL and want it on Render (instead of only bootstrap admin):

1. Ensure first deploy finished (`flask db upgrade` on Render).
2. Follow [migrate-local-db-to-render.md](migrate-local-db-to-render.md) — `backend/scripts/push_db_to_render.ps1`.
3. Copy `TOKEN_ENCRYPTION_KEY` (and `SECRET_KEY` if used for encryption fallback) from local `.env` to Render env when I-9/W-4/integrations were encrypted locally.
4. Copy `backend/instance/` uploads separately (or sync to B2 per [backblaze-b2.md](backblaze-b2.md)); they are not in the DB dump.

Skip this section if you are starting fresh and only need a bootstrap user (step 5).

## 5. Bootstrap staff user

Render Shell (service `usis-cm`, root `backend/`):

```bash
python scripts/create_bootstrap_admin.py
```

Uses `BOOTSTRAP_ADMIN_EMAIL` / `BOOTSTRAP_ADMIN_PASSWORD` from the environment.

## 6. Smoke test

Replace `https://usis-cm.onrender.com` with your service URL (`RENDER_EXTERNAL_URL`).

| Check | URL |
|-------|-----|
| Health | `GET /healthz` → `{"status":"ok",...}` |
| Public apply | `/apply.html` |
| Register / hire | Apply → register → `/usis-hr-hire.html` |
| Staff login | `/page-login.html` → dashboard |

In browser DevTools → Network, API calls should go to **same origin** (not `127.0.0.1:5000`).

## 7. Employee testing entry points

| Audience | Start here |
|----------|------------|
| Job applicants | `/apply.html` |
| Staff | `/page-login.html` |

## Troubleshooting

- **502 on static pages**: Build failed or `USIS_STATIC_ROOT` wrong — confirm `gulp/dist` exists in build logs.
- **API NetworkError / CORS**: `CORS_ORIGINS` must match the browser origin exactly (scheme + host, no trailing path).
- **Uploads lost after redeploy**: Use B2 ([backblaze-b2.md](backblaze-b2.md)) or confirm persistent disk is mounted at `backend/instance`.
- **I-9 / W-4 errors**: Set `TOKEN_ENCRYPTION_KEY` (Fernet); do not change it after data is stored.

## Local production-like test

```powershell
cd W3CRM-v3.0-13_September_2025\gulp
npm ci
npx gulp build
cd ..\..\backend
$env:FLASK_ENV="production"
$env:USIS_STATIC_ROOT="..\W3CRM-v3.0-13_September_2025\gulp\dist"
gunicorn wsgi:app --bind 127.0.0.1:5000
```

Open `http://127.0.0.1:5000/apply.html` (same-origin API).
