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
| `CORS_ORIGINS` | Auto from `USIS_APP_PUBLIC_URL`, else `RENDER_EXTERNAL_URL` |
| `USIS_POST_LOGIN_REDIRECT` | `{USIS_APP_PUBLIC_URL}/usis-dashboard.html` if public URL set, else Render default |
| `USIS_APP_PUBLIC_URL` | Canonical HTTPS origin (required for custom domain; see §8) |

### Object storage (Backblaze B2, recommended for production uploads)

Set all four **required** variables to store drawings, spec PDFs, RFI attachments, and HR document photos in B2 instead of the Render disk. Full setup: [backblaze-b2.md](backblaze-b2.md).

**Your bucket:** `USIS-construction-docs` (private, default encryption on). The app does not expose a public bucket URL; authenticated users download through Flask after login.

**Credentials:** Backblaze gives **keyID** and **applicationKey** (two fields). Do not use a single env var such as `back_blaze` — delete it on Render if present and use the table below.

| Variable | Value to enter on Render |
|----------|---------------------------|
| `B2_APPLICATION_KEY_ID` | Application key **keyID** from B2 (e.g. `003…`) |
| `B2_APPLICATION_KEY` | Application key **applicationKey** secret (paste once; treat as password) |
| `B2_BUCKET_NAME` | `USIS-construction-docs` |
| `B2_ENDPOINT` | Copy **S3 Endpoint** from B2 → bucket **USIS-construction-docs** → Bucket Settings (e.g. `https://s3.us-west-004.backblazeb2.com`) |
| `B2_PREFIX` | Optional, e.g. `prod/usis-cm` |

After saving env vars, trigger **Manual Deploy** (or push to `main`) so the service restarts with B2 enabled. New uploads use B2; existing files on the Render disk are not migrated automatically ([backblaze-b2.md](backblaze-b2.md) §6).

If any B2 secret was pasted in chat or committed, **rotate** the application key in Backblaze and update Render env vars.

### Email (invites, RFI, playbooks)

Transactional mail uses SMTP env vars (SendGrid recommended). Without them, the app logs **dry-run** and does not send. Full setup, flows, and troubleshooting: **[email.md](email.md)**.

| Variable | Example (SendGrid) |
|----------|-------------------|
| `MAIL_SERVER` | `smtp.sendgrid.net` |
| `MAIL_PORT` | `587` |
| `MAIL_USERNAME` | `apikey` |
| `MAIL_PASSWORD` | *(API key — secret)* |
| `MAIL_FROM` | `noreply@yourdomain.com` |
| `USIS_APP_PUBLIC_URL` | `https://your-service.onrender.com` |
| `USIS_SEND_USER_INVITE_EMAIL` | `1` to email new users from User admin |

Staff invites: **User admin** (`/usis-user-directory.html`) or `POST /api/v1/admin/users` with `"send_invite": true`. Applicant self-register (`/apply.html`) does **not** send email today.

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

Replace `https://usis-cm.onrender.com` with your public URL (`USIS_APP_PUBLIC_URL` or `RENDER_EXTERNAL_URL`).

| Check | URL |
|-------|-----|
| Health | `GET /healthz` → `{"status":"ok",...}` |
| Site root | `/` → redirects to `/page-login.html` (staff sign-in) |
| Public apply | `/apply.html` |
| Register / hire | Apply → register → `/usis-hr-hire.html` |
| Staff login | `/page-login.html` → dashboard |

In browser DevTools → Network, API calls should go to **same origin** (not `127.0.0.1:5000`).

## 7. Custom domain (e.g. www.usiscm.com)

Use a custom domain when you own DNS (e.g. `usiscm.com`) and want staff/applicants on your brand URL instead of `*.onrender.com`. The app serves UI and API on **one origin**; session cookies and `usis-api-base-default.js` rely on that.

### 7.1 Render Dashboard

1. [Render Dashboard](https://dashboard.render.com) → **usis-cm** → **Settings** → **Custom Domains**
2. **Add custom domain** → `www.usiscm.com` → save. Render shows DNS instructions and a target hostname (e.g. `usis-cm.onrender.com` — use the value shown in the dashboard).
3. Optional apex: add `usiscm.com` if you want bare-domain access. Render may offer **redirect** from apex → `www` (recommended so you have one canonical origin).
4. Wait until domain status is **Verified** and **Certificate issued** (Let’s Encrypt; automatic, no upload).

### 7.2 DNS at your registrar

Use the exact hostnames Render displays for your service.

| Host | Type | Value |
|------|------|--------|
| `www` | `CNAME` | Render hostname from step 7.1 (e.g. `usis-cm.onrender.com`) |
| `@` (apex) | `A` / `ALIAS` / `ANAME` | Per Render’s apex instructions for your registrar (or enable Render’s apex → `www` redirect and only serve `www`) |

TTL: default is fine. Propagation can take up to 48 hours; often minutes.

### 7.3 Environment variables (after DNS is live)

Set in **usis-cm** → **Environment** (then **Save** and redeploy if the service does not restart automatically):

| Variable | Example | Notes |
|----------|---------|--------|
| `USIS_APP_PUBLIC_URL` | `https://www.usiscm.com` | No trailing slash. Drives invite/login email links, default CORS, and post-login redirect. |
| `USIS_POST_LOGIN_REDIRECT` | *(optional)* `https://www.usiscm.com/usis-dashboard.html` | Only if you need a path other than the default. |
| `CORS_ORIGINS` | *(optional)* `https://www.usiscm.com` | Only if you serve the app on **multiple** origins (e.g. `https://www.usiscm.com,https://usiscm.com`). With a single canonical host, leave unset when `USIS_APP_PUBLIC_URL` is set. |

`RENDER_EXTERNAL_URL` remains `https://<service>.onrender.com` and is **not** updated for custom domains. Do not rely on it alone after adding `www.usiscm.com`.

Also update third-party redirect URIs if used:

| Integration | Variable | Example |
|-------------|----------|---------|
| Microsoft Entra SSO | `MS_ENTRA_REDIRECT_URI` | `https://www.usiscm.com/auth/microsoft/callback` |
| Autodesk / BuildingConnected | `AUTODESK_OAUTH_REDIRECT_URI` | `https://www.usiscm.com/api/v1/integrations/buildingconnected/oauth/callback` |
| Power BI embed (reports page) | `POWERBI_TENANT_ID`, `POWERBI_CLIENT_ID`, `POWERBI_CLIENT_SECRET`, `POWERBI_WORKSPACE_ID`, `POWERBI_REPORT_ID` | Service principal; see [powerbi-embed.md](powerbi-embed.md) |

### 7.4 Smoke test on custom domain

| Check | URL |
|-------|-----|
| Health | `https://www.usiscm.com/healthz` |
| Site root | `https://www.usiscm.com/` → `/page-login.html` |
| Apply | `https://www.usiscm.com/apply.html` |
| Login | `https://www.usiscm.com/page-login.html` |

In DevTools → Network, API requests should stay on `https://www.usiscm.com` (not `127.0.0.1:5000` or `*.onrender.com` unless you intentionally split hosts).

## 8. Employee testing entry points

| Audience | Start here |
|----------|------------|
| Job applicants | `/apply.html` |
| Staff | `/page-login.html` |

## Troubleshooting

- **502 on static pages**: Build failed or `USIS_STATIC_ROOT` wrong — confirm `gulp/dist` exists in build logs.
- **API NetworkError / CORS**: `CORS_ORIGINS` (or `USIS_APP_PUBLIC_URL` when CORS is unset) must match the browser origin exactly (scheme + host, no trailing path). After a custom domain, set `USIS_APP_PUBLIC_URL` — `RENDER_EXTERNAL_URL` alone will not match `www.usiscm.com`.
- **Login loops / wrong redirect**: Set `USIS_APP_PUBLIC_URL=https://www.usiscm.com` so post-login and `?next=` redirects use the custom host.
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
