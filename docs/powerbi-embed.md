# Power BI embed (reports page)

The **Reports** page (`reports.html`) embeds one report via `GET /api/v1/powerbi/embed-config`. The Flask API uses a **service principal** (Azure app registration) with the client-credentials flow, then calls Power BI **GenerateToken** for a view-only embed.

## 1. Azure app registration

1. Open [Microsoft Entra admin center](https://entra.microsoft.com/) → **App registrations** → **New registration**.
2. Name it (e.g. `USIS CM Power BI embed`). Supported account types: **Single tenant**.
3. After create, copy:
   - **Application (client) ID** → `POWERBI_CLIENT_ID`
   - **Directory (tenant) ID** → `POWERBI_TENANT_ID`
4. **Certificates & secrets** → **New client secret** → copy the value once → `POWERBI_CLIENT_SECRET`.

### API permissions (application)

1. **API permissions** → **Add a permission** → **Power BI Service** → **Application permissions**.
2. Add **Report.Read.All** (minimum for read + embed token). If GenerateToken fails with 403, also add **Workspace.Read.All** and grant admin consent again.
3. **Grant admin consent** for your tenant.

## 2. Power BI admin tenant setting

A Power BI **admin** must enable service principals:

1. [Power BI admin portal](https://app.powerbi.com/admin-portal/tenantSettings) → **Tenant settings**.
2. **Developer settings** → **Allow service principals to use Power BI APIs** → **Enabled**.
3. Either enable for the **entire organization** or add your app’s **Application (client) ID** under a security group / specific SP list (match your org policy).

## 3. Workspace access

The service principal must access the workspace that holds the report:

1. In [Power BI](https://app.powerbi.com/), open the **workspace** (not “My workspace” unless the report lives there).
2. **Manage access** → **Add people** → search for the **app registration name** (same as step 1 above) → role **Member** or **Admin**.
3. Publish or confirm the report exists in that workspace.

Without this step, token or Get Report calls return **403**.

## 4. Workspace and report IDs

**Option A — discovery script (recommended)**

After `POWERBI_TENANT_ID`, `POWERBI_CLIENT_ID`, and `POWERBI_CLIENT_SECRET` are in `backend/.env`:

```powershell
cd E:\programs\USIS_CM\backend
.\.venv\Scripts\Activate.ps1
python scripts\powerbi_discover.py
```

Copy the printed **workspace id** and **report id** into `.env` as `POWERBI_WORKSPACE_ID` and `POWERBI_REPORT_ID`.

**Option B — Power BI UI**

1. Open the report in the browser. The URL looks like:
   `https://app.powerbi.com/groups/{WORKSPACE_ID}/reports/{REPORT_ID}/...`
2. Use those GUIDs for `POWERBI_WORKSPACE_ID` and `POWERBI_REPORT_ID`.

## 5. Local API environment

In `backend/.env` (see `.env.example`):

```env
POWERBI_TENANT_ID=<directory-tenant-guid>
POWERBI_CLIENT_ID=<application-client-id>
POWERBI_CLIENT_SECRET=<client-secret-value>
POWERBI_WORKSPACE_ID=<workspace-group-guid>
POWERBI_REPORT_ID=<report-guid>
```

Restart Flask so the process reloads env (`.env` is read at startup):

```powershell
# Stop the existing flask run on :5000, then:
cd E:\programs\USIS_CM\backend
.\.venv\Scripts\Activate.ps1
$env:FLASK_APP = "app:create_app"
$env:FLASK_ENV = "development"
flask run --host 127.0.0.1 --port 5000
```

Smoke test (while logged in as a user with a standard role, or with dev headers if enabled):

```text
GET http://127.0.0.1:5000/api/v1/powerbi/embed-config
```

Expect `"configured": true` and `embedUrl` / `embedToken` in JSON.

Open `reports.html` from Gulp/BrowserSync with `USIS_API_BASE` pointing at Flask (`http://127.0.0.1:5000`).

## 6. Production (Render)

On the **usis-cm** web service, set the same five variables under **Environment**, save, and redeploy. Do not commit secrets.

| Variable | Notes |
|----------|--------|
| `POWERBI_TENANT_ID` | Tenant GUID |
| `POWERBI_CLIENT_ID` | App registration client id |
| `POWERBI_CLIENT_SECRET` | Client secret (rotate in Entra if leaked) |
| `POWERBI_WORKSPACE_ID` | Workspace (group) id |
| `POWERBI_REPORT_ID` | Report id in that workspace |

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `configured: false`, `missing_env` | One or more `POWERBI_*` vars empty; restart Flask after editing `.env`. |
| `Azure AD token failed (401)` | Wrong tenant, client id, or secret. |
| `Get Report failed (403)` | SP not added to workspace, or tenant setting blocks service principals. |
| `GenerateToken failed (403)` | Missing API permission or admin consent; try **Report.Read.All** + workspace Member. |
| Browser shows HTML 404 for `/api/v1/powerbi/...` | Static server only — set `USIS_API_BASE` / meta tag to Flask origin. |
