# Email (transactional SMTP)

USIS sends outbound mail over **SMTP** using Python’s stdlib (`smtplib`) in `backend/app/api/_notifications.py`. `Flask-Mail` is listed in `requirements.txt` for future use but is **not** wired today.

Without SMTP env vars, the app still runs: emails are **logged as dry-run** and RFI notification rows are marked delivered without sending.

## Recommended provider on Render

Use a transactional SMTP relay (not Render’s platform mail):

| Provider | Why |
|----------|-----|
| **[SendGrid](https://sendgrid.com)** (recommended) | Mature SMTP API, free tier, domain authentication, works with existing `MAIL_*` vars |
| **[Resend](https://resend.com)** | Simple SMTP (`smtp.resend.com`) |
| **[Mailgun](https://www.mailgun.com)** | SMTP relay + good deliverability |

Steps (SendGrid example):

1. Create a SendGrid account → **Settings → API Keys** (for API) or use **SMTP**.
2. **Settings → Sender Authentication** → verify your domain (or single sender for testing).
3. In SendGrid: **Settings → SMTP** → note host `smtp.sendgrid.net`, port **587**, username **`apikey`**, password = your API key.
4. On Render → **usis-cm → Environment**, set the variables below.
5. **Manual Deploy** (or push) so Gunicorn picks up new env.

## Environment variables

Set these on Render (and in local `backend/.env` for testing):

| Variable | Required | Example (SendGrid) | Notes |
|----------|----------|-------------------|--------|
| `MAIL_SERVER` | Yes | `smtp.sendgrid.net` | SMTP hostname |
| `MAIL_PORT` | No | `587` | Default `587` |
| `MAIL_USE_TLS` | No | `true` | Set `false` only if provider uses plain SMTP on 25/465 |
| `MAIL_USERNAME` | Yes | `apikey` | SendGrid SMTP user is literally `apikey` |
| `MAIL_PASSWORD` | Yes | *(API key)* | Treat as secret; never commit |
| `MAIL_FROM` | Yes | `noreply@yourdomain.com` | Must be a verified sender in your provider |

Optional (links inside invite / notification bodies):

| Variable | Purpose |
|----------|---------|
| `USIS_APP_PUBLIC_URL` | Public site origin, e.g. `https://usis-cm.onrender.com` (no trailing slash). Overrides login link derivation. |
| `USIS_POST_LOGIN_REDIRECT` | Used to infer origin if `USIS_APP_PUBLIC_URL` unset (see `backend/app/config.py`) |
| `RENDER_EXTERNAL_URL` | Auto on Render; used as fallback for login links |
| `USIS_SEND_USER_INVITE_EMAIL` | If `1` / `true`, send invite mail on every `POST /api/v1/admin/users` (default off) |

Async RFI dispatch (optional, not required on Render for low volume):

| Variable | Purpose |
|----------|---------|
| `CELERY_BROKER_URL` | e.g. `redis://...` — if set, RFI emails use Celery task `rfi.send_email` |
| `CELERY_RESULT_BACKEND` | Defaults to broker |

Render does **not** provision Redis in `render.yaml`; for MVP, leave Celery unset and RFI mail sends **inline** in the web process.

## What sends email today

| Flow | Trigger | Sends when SMTP configured? |
|------|---------|-------------------------------|
| **RFI notifications** | RFI create/update/forward; `POST /api/v1/rfis/<id>/email` | Yes (log row + SMTP; Celery if broker set) |
| **Playbooks** | Checklist run start / reassignment | Yes (`send_plain_notification_email`) |
| **Admin user invite** | `POST /api/v1/admin/users` with `"send_invite": true` or `USIS_SEND_USER_INVITE_EMAIL=1` | Yes (new) |
| **Self-register / hire** | `POST /api/v1/auth/register`, `/apply.html` | **No** — account only, no verification email |
| **Password reset** | — | **Not implemented** |
| **core-hr “Invite Employee” modal** | W3CRM template UI | **Not wired** — use **User admin** (`usis-user-directory.html`) instead |
| **Microsoft SSO** | Entra login | **No email** — identity via Microsoft |
| **HRMS in-app notifications** | DB table `hrms_notifications` | **In-app only** — no SMTP yet |

## User invite flow (staff)

1. Configure SMTP on Render (table above).
2. Set `USIS_APP_PUBLIC_URL` to your Render URL (or rely on `RENDER_EXTERNAL_URL`).
3. Sign in as admin → **User admin** (`/usis-user-directory.html`) → **Add user**.
4. Either:
   - Set env `USIS_SEND_USER_INVITE_EMAIL=1` so every new user gets mail, or
   - Pass JSON `"send_invite": true` on `POST /api/v1/admin/users` (API / future UI checkbox).

Example API body:

```json
{
  "email": "new.hire@company.com",
  "first_name": "Alex",
  "last_name": "Rivera",
  "password": "temporary-change-me",
  "role_ids": ["<role-uuid>"],
  "send_invite": true
}
```

Invite body includes `/page-login.html` on your public origin. If you set a password in the request, the email says to change it after first login.

## Applicant / hire flow (no invite email)

- **`/apply.html`** → `POST /api/v1/auth/register` when `USIS_ALLOW_SELF_REGISTER=1` (default on Render per `render.yaml`).
- User chooses password in the browser; **no** confirmation email is sent.
- Hire wizard: `/usis-hr-hire.html` after register (session cookie).

For applicants, email is optional product work (verification, magic link, etc.) — not in scope of current code.

## Local smoke test

```powershell
cd E:\programs\USIS_CM\backend
# Add MAIL_* to .env, then:
$env:FLASK_APP="app:create_app"
flask shell
```

```python
from app.api._notifications import send_plain_notification_email
send_plain_notification_email(to="you@company.com", subject="USIS test", body="SMTP works.")
```

Check provider dashboard for delivery/bounces.

## Troubleshooting

- **No mail, no error**: SMTP vars missing — search logs for `dry-run`.
- **Authentication failed**: Wrong `MAIL_USERNAME` / `MAIL_PASSWORD` (SendGrid must use user `apikey`).
- **Sender rejected**: `MAIL_FROM` not verified in provider.
- **RFI “sent” but inbox empty**: Check `rfi_notification_log` and app logs; Celery worker must run if `CELERY_BROKER_URL` is set.
- **Invite not sent**: `send_invite` false and `USIS_SEND_USER_INVITE_EMAIL` unset.

See also [render-deploy.md](render-deploy.md) § Email.
