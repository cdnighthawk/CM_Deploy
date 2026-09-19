# Estimate folder provisioning

When someone creates an estimate in CM, the API also provisions a real project
folder tree on the company file store. That folder is the destination for
BidDocProcessor / bid-doc copies and later CM ingest. Folder creation is part
of the estimate-created flow — not a separate manual step.

Production CM typically runs on Render. The large project share lives on
Charles’s Windows data server (`C:\usis-cm`, `Z:`). The web process must **not**
assume it can write `Z:\`. Prefer an authenticated HTTP call to an on-prem
agent that can see the share.

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
| `ESTIMATE_FOLDER_PROVISION_URL` | Base URL of the data-server agent. CM POSTs `{url}/provision/estimate-folder`. If the value already ends with that path, it is not duplicated. |
| `ESTIMATE_FOLDER_PROVISION_TOKEN` | Shared secret sent as header `X-USIS-Provision-Token`. |
| `ESTIMATE_FOLDER_PROVISION_TIMEOUT_SEC` | HTTP timeout (default `20`, max `120`). |
| `ESTIMATE_FOLDER_ROOT` | Direct `mkdir` only when this path exists and is writable (local/dev). Do **not** set this to `Z:\` on Render. |

If both URL and root are set, CM calls the agent first and falls back to local
mkdir only when the HTTP call fails. If neither is set, create still succeeds
and provision is skipped (logged).

Also listed in `backend/.env.example`.

## Folder template

Created under `{root}/{job_or_id} - {name}/` (Windows-safe name):

```
{job_or_id} - {name}/
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

`job_or_id` is the lead `number`, else the project `number`, else the estimate
UUID. `name` is the estimate name. The root folder includes a short
`README.txt` explaining the tree.

Idempotent: if the folder already exists, the call succeeds and returns the
path (`created: false`).

## Data-server agent contract

The Windows agent implementation may live on the data server separately. CM
expects:

```
POST /provision/estimate-folder
```

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
  "path": "Z:\\Projects\\23044 - Turner – Bid Set",
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
