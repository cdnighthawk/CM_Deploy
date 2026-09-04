# Email

USIS sends mail through **Microsoft Graph** using the same Entra app as Microsoft sign-in (`backend/app/api/_notifications.py`). SMTP remains a fallback if `MAIL_TRANSPORT=smtp`.

From addresses:

1. **Staff mail** — compose and RFI forward send as the **signed-in user's** `gousis.com` mailbox (appears in their Outlook Sent Items).
2. **System mail** — password reset, user invites, playbooks, and HR letters send as **`MAIL_FROM`** (use `noreply@gousis.com`).
3. **RFP quotes** — invitations send as **`quotes@gousis.com`** (`QUOTES_MAILBOX`) with Reply-To the same mailbox so vendor replies land there. AP invoices continue to use **`invoices@gousis.com`**.

Without Graph (or SMTP) env vars, the app still runs: emails are **logged as dry-run**.

## Microsoft 365 setup

1. In Entra, on the **USIS CRM** app (`738dce41-ed61-4475-82ae-5800963231c0`): **API permissions** → **Microsoft Graph** → **Application permissions**:
   - `Mail.Send` (compose + system mail)
   - `Mail.ReadWrite` (Inbox, Sent, read, delete on the website)
2. Click **Grant admin consent** for the tenant.
3. Create shared mailboxes `noreply@gousis.com`, `quotes@gousis.com`, and `invoices@gousis.com` in Microsoft 365 admin (no extra license).
4. Restrict the app with an Exchange **application access policy** so it can only access `@gousis.com` mailboxes plus those shared mailboxes. After creating a new mailbox, re-run [exchange-application-access-policy.ps1](exchange-application-access-policy.ps1) so the Graph app can Send As / read it.
5. On Render set `MAIL_TRANSPORT=graph` and `MAIL_FROM=noreply@gousis.com`. Existing `MS_ENTRA_*` vars are reused.

The website always uses the **signed-in user’s** mailbox address — never a mailbox chosen by the client. The access policy is the tenant-side limit.

Staff open **Email** in the left menu (`usis-email.html`): Inbox, Sent, read, delete, and compose. That page calls `GET/PATCH/DELETE /api/v1/mail/messages` and `POST /api/v1/messages/email`.

**AP invoices:** `POST /api/v1/ap/mailbox/sync` reads `invoices@gousis.com`. The web process also polls that mailbox every 5 minutes (`INVOICE_MAILBOX_SYNC_INTERVAL_SEC`, default `300`). Production has a Render cron (`usis-invoice-mailbox-sync`) that POSTs the same route with `X-Cron-Secret`.

## Environment variables

| Variable | Required | Example | Notes |
|----------|----------|---------|--------|
| `MAIL_TRANSPORT` | No | `graph` | `graph` (default when Entra is set), or `smtp` |
| `MAIL_FROM` | Yes for system mail | `noreply@gousis.com` | Shared mailbox for password reset / invites |
| `QUOTES_MAILBOX` | No | `quotes@gousis.com` | RFP invitations From / Reply-To and inbound quote ingest |
| `INVOICE_MAILBOX` | No | `invoices@gousis.com` | AP invoice ingest |
| `INVOICE_MAILBOX_SYNC_INTERVAL_SEC` | No | `300` | In-process poll of `invoices@`; `0` disables (Render cron still runs) |
| `MAIL_ALLOWED_FROM_DOMAINS` | No | `gousis.com` | Staff send-as is limited to these domains |
| `MS_ENTRA_TENANT_ID` / `CLIENT_ID` / `CLIENT_SECRET` | Yes for Graph | *(already on Render)* | Same app as Microsoft login |

SMTP fallback (only if `MAIL_TRANSPORT=smtp`):

| Variable | Example |
|----------|---------|
| `MAIL_SERVER` | `smtp.sendgrid.net` |
| `MAIL_PORT` | `587` |
| `MAIL_USERNAME` | `apikey` |
| `MAIL_PASSWORD` | *(API key)* |


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
| **RFP invitations** | RFP detail **Send invitations** → `POST /api/v1/rfps/<id>/send` | Yes — from `quotes@gousis.com`; replies ingested by **Sync quotes mailbox** |
| **Issue status (feedback)** | `Resolution:` comment or team close → `POST /api/webhooks/github` | Yes — employee then closes the issue to confirm |
| **RFI notifications** | RFI create/update/forward; `POST /api/v1/rfis/<id>/email` | Yes (log row + SMTP; Celery if broker set) |
| **Playbooks** | Checklist run start / reassignment | Yes (`send_plain_notification_email`) |
| **Admin user invite** | `POST /api/v1/admin/users` with `"send_invite": true` or `USIS_SEND_USER_INVITE_EMAIL=1` | Yes (new) |
| **Self-register / hire** | `POST /api/v1/auth/register`, `/apply.html` | **No** — account only, no verification email |
| **Password reset** | `page-forgot-password.html` → `POST /api/v1/auth/password-reset/request` | Yes when SMTP configured |
| **core-hr “Invite Employee” modal** | W3CRM template UI | **Not wired** — use **User admin** (`usis-user-directory.html`) instead |
| **Microsoft SSO** | Entra login | **No email** — identity via Microsoft |
| **HRMS in-app notifications** | DB table `hrms_notifications` | **In-app only** — no SMTP yet |

### Issue status emails

The employee confirms a report is resolved by closing it.

1. Set `GITHUB_WEBHOOK_SECRET` on Render (and in local `.env` if you test webhooks).
2. In `cdnighthawk/CM_Deploy` → Settings → Webhooks, add `https://www.usiscm.com/api/webhooks/github`, secret matching the env var, events: **Issues** and **Issue comments**.
3. Leave a comment that starts with `Resolution:` and leave the issue **open**.
4. The reporter gets an email with a link to close the issue or mark it still not fixed. If someone else closes it first, USIS reopens it until the reporter confirms.

Existing reports that already include `**Email:**` in the issue body are included — no need to re-file them.

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
