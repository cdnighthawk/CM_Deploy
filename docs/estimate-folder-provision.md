# Estimate folder provisioning

When someone creates an estimate in CM, the API also provisions a real project
folder tree on the company file store. That folder is the destination for
BidDocProcessor / bid-doc copies and later CM ingest. Folder creation is part
of the estimate-created flow — not a separate manual step.

Production CM typically runs on Render. Estimate folders live on the Windows
data server at **`Y:\Estimates`** (not `Z:`). The web process must **not**
assume it can write `Y:\`. Prefer an authenticated HTTP call to the on-prem
agent that can see that share:

- Script: `C:\usis-cm\folder_provision.py`
- Listen port: **5055**
- Root: `Y:\Estimates`

## CM hooks

After a successful DB commit of a new `estimates` row:

| Path | How a row is created |
| --- | --- |
| `POST /api/v1/leads/<id>/estimates` | `_estimate_service.create_estimate` (independent estimate) |
| `POST /api/v1/lead-estimates/<id>/estimates` | same |
| `POST /api/v1/estimates` | `extra_plan_routes.create_estimate` (lead or project) |
| First takeoff / lock / approve / door-schedule line when no estimate exists | `_estimate_service.ensure_current_estimate` (lead → estimate) |

The service queues work on the SQLAlchemy session (`schedule_estimate_folder_provision`)
and runs it in `after_commit`. A failed provision **does not** roll back the
estimate. Retry:

```
POST /api/v1/estimates/<estimate_id>/provision-folder
```

Admin / superuser (or `USIS_API_DEV_ALLOW_ANY` in local dev). Same body/result
shape as the agent response, plus the estimate item.

## Environment

| Variable | Purpose |
| --- | --- |
| `ESTIMATE_FOLDER_PROVISION_URL` | Base URL of the data-server agent (live: port **5055**). CM POSTs `{url}/provision/estimate-folder`. If the value already ends with that path (or an alias: `/provision/estimate-folders`, `/estimate-folder`), it is not duplicated. |
| `ESTIMATE_FOLDER_PROVISION_TOKEN` | Shared secret sent as header `X-USIS-Provision-Token`. Must match `folder_provision.py`. |
| `ESTIMATE_FOLDER_PROVISION_TIMEOUT_SEC` | HTTP timeout (default `20`, max `120`). Optional. |
| `ESTIMATE_FOLDER_ROOT` | On-prem root. Canonical value is `Y:\Estimates`. Direct `mkdir` only when this path exists and is writable (local/dev). Do **not** set this on Render. |

If both URL and root are set, CM calls the agent first and falls back to local
mkdir only when the HTTP call fails. If neither is set, create still succeeds
and provision is skipped (logged).

Also listed in `backend/.env.example`.

### Render (`usis-cm`) — Charles checklist

Set these on **Dashboard → usis-cm → Environment**, then redeploy. The URL must
be reachable from Render (public hostname, tunnel, or VPN) — not `127.0.0.1`
and not a LAN-only address unless Render can route to it.

| Set on Render | Example / notes |
| --- | --- |
| `ESTIMATE_FOLDER_PROVISION_URL` | `http://<data-server-host>:5055` (or the full `http://<host>:5055/provision/estimate-folder`) |
| `ESTIMATE_FOLDER_PROVISION_TOKEN` | Same shared secret the live agent expects |

Do **not** set `ESTIMATE_FOLDER_ROOT` on Render. Optional: `ESTIMATE_FOLDER_PROVISION_TIMEOUT_SEC=20`.

On the data server, keep `C:\usis-cm\folder_provision.py` listening on **5055**
with root **`Y:\Estimates`**.

## Folder template

Created under `{root}/{job} - {name}/` (Windows-safe name). On the data
server, `{root}` is **`Y:\Estimates`**:

```
{job} - {name}/
  README.txt
  01_Bid_Docs/
  02_Processed/
    drawings/
    specs/
    other/
  03_Takeoff/
  04_Correspondence/
  05_Reports/
```

`{job}` is the lead `number`, else the project `number`, else the estimate
UUID. `name` is the estimate name. The root folder includes a short
`README.txt` explaining the tree.

The Windows ingest agent should **read** `folder_path` from
[`docs/ingest-estimate-sync.md`](ingest-estimate-sync.md)
(`GET /api/ingest/estimates` with `CM_API_KEY`). Do not add a second provisioner.

Idempotent: if the folder already exists, the call succeeds and returns the
path (`created: false`).

## Data-server agent contract

Live agent: `C:\usis-cm\folder_provision.py` on port **5055**, root
`Y:\Estimates`. CM POSTs:

```
POST /provision/estimate-folder
```

Aliases accepted by CM when `ESTIMATE_FOLDER_PROVISION_URL` already includes
them (not appended again): `/provision/estimate-folders`, `/estimate-folder`.
The local stub accepts the same paths.

Headers:

- `Content-Type: application/json`
- `X-USIS-Provision-Token: <ESTIMATE_FOLDER_PROVISION_TOKEN>`

JSON body (required keys; extra keys may be present):

```json
{
  "estimate_id": "uuid",
  "job_number": "23044",
  "name": "Turner – Bid Set",
  "project_uuid": "uuid or null",
  "requested_by": "user@gousis.com"
}
```

CM also sends (optional, ignore if unused): `folder_name`, `office`,
`lead_estimate_id`, `template`.

Success response:

```json
{
  "ok": true,
  "path": "Y:\\Estimates\\23044 - Turner – Bid Set",
  "created": true
}
```

`created` is `true` when the project folder was newly created, `false` when it
already existed. On failure return a non-2xx status and/or `"ok": false` with
an `error` string. CM stores `folder_provision_status`, `folder_path`,
`folder_provisioned_at`, and `folder_provision_error` on the estimate.

## Local stub

For tests and local HTTP without the Windows agent:

```
cd backend
python scripts/estimate_folder_provision_stub.py --root /tmp/usis-estimate-folders --token dev-token
```

Then:

```
ESTIMATE_FOLDER_PROVISION_URL=http://127.0.0.1:8741
ESTIMATE_FOLDER_PROVISION_TOKEN=dev-token
```

The stub implements this contract and mkdirs the template under `--root`.
