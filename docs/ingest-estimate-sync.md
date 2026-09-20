# Desktop ingest: estimate folder map

Read-only API so the Windows ACCDocs/Forma agent can file Phase A breakapart
sheets under the provisioned estimate folder (`Y:\Estimates\{job} - {name}`)
instead of `C:\usis-cm\data\library\{project_key}`.

This does **not** create folders. Folder trees are still provisioned when CM
creates an estimate (see [estimate-folder-provision.md](estimate-folder-provision.md),
PR #53). The agent only **reads** `estimates.folder_path`.

Do not use staff session route `GET /api/v1/estimates` from the agent — that
requires a signed-in user and returns 401 for `CM_API_KEY`.

## URL

```
GET https://www.usiscm.com/api/ingest/estimates
```

Alias (same handler, next to `GET /api/projects`):

```
GET https://www.usiscm.com/api/estimates
```

Idempotent GET. No request body. No multipart / upload changes.

## Auth

Same Bearer pattern as `POST /api/ingest/events` and `GET /api/projects`.

```
Authorization: Bearer <CM_API_KEY>
```

`CM_INGEST_API_KEY` is also accepted when set. Missing configured key → **503**.
Missing or wrong token → **401**.

## Query

| Param | Purpose |
| --- | --- |
| `q` | Search. Also accepted as `folder`, `project_key`, or `project_number`. Matches estimate id, job/lead/project numbers and names, `folder_path`, and linked project ids. `PROJ-2024-0142` normalizes to `240142` (same as ingest project match). |
| `project_id` | Filter to a CM `projects.id` **or** `lead_estimates.id` (the agent sometimes stores a lead UUID as `project_id`). |
| `folder_provision_status` | Exact status (`ready`, `failed`, `unconfigured`, …). Alias: `status`. |
| `has_folder` | `1`/`true` = only rows with `folder_path`. `0`/`false` = only rows without. |
| `due_from` | Inclusive lower bound on bid due (`due_at`). ISO date (`YYYY-MM-DD`, UTC midnight) or datetime. Alias: `due_after`. |
| `due_to` | Inclusive upper bound on bid due (`due_at`). Date-only values include the whole UTC day. Alias: `due_before`. Omit for any future date. |
| `limit` | Page size (default **500**, max **2000**). |
| `offset` | Skip N filtered rows (default **0**). |

Invalid `limit` / `offset` / `due_from` / `due_to` → **400**. `due_from` after `due_to` → **400**.

Rows with a null `due_at` are omitted when either due bound is set.

**Desktop window (today − 30 days through any future date):**

```
GET /api/ingest/estimates?due_from=2026-08-21
Authorization: Bearer $CM_API_KEY
```

Use `due_from=<today minus 30 days>` and omit `due_to`. Same `due_from` / `due_to` names as `GET /api/v1/lead-estimates`.

## Response

```json
{
  "estimates": [
    {
      "id": "8f1c0b2a-…",
      "name": "Original Estimate",
      "job_number": "26061",
      "folder_path": "Y:\\Estimates\\26061 - Original Estimate",
      "folder_provision_status": "ready",
      "folder_provisioned_at": "2026-09-19T21:04:00+00:00",
      "is_current": true,
      "lead_estimate_id": "c3aa…",
      "lead_number": "26061",
      "lead_name": "Civic Center",
      "project_id": "b91e…",
      "project_number": "26061",
      "project_name": "Civic Center",
      "projects": [
        {"id": "b91e…", "number": "26061", "name": "Civic Center"}
      ],
      "folder_hints": ["26061", "Civic Center", "Original Estimate"],
      "archived": false,
      "due_at": "2026-09-30T17:00:00+00:00",
      "updated_at": "2026-09-19T21:04:00+00:00"
    }
  ],
  "count": 1,
  "limit": 500,
  "offset": 0,
  "has_more": false,
  "entity": "ingest_estimates"
}
```

`due_at` is the bid-due timestamp. The column name is **`due_at`** (not
`submitted_at` / `bid_due_at`). Source:

1. `estimates.due_at` when set (copied from the lead when the estimate is created)
2. else `lead_estimates.due_at` (BuildingConnected CSV **`dueAt`**)

There is **no** submitted-date column on `estimates` or `lead_estimates`.
“Submitted” is `lead_estimates.submission_state` (`SUBMITTED`, `WILL_SUBMIT`,
`UNDECIDED`, …), not a timestamp.

`job_number` is `lead_estimates.number`, else `projects.number`. It is **never**
the estimate UUID (and a UUID stored in a number column is ignored). If neither
human number exists, `job_number` is `null` — do not invent a folder name.

`folder_path` is the provisioned path from CM (`folder_provision_status=ready`
when the data-server agent succeeded). `null` means the folder was never
written on the estimate; keep the library fallback.

Scan is capped at 5000 newest estimates (after `due_from` / `due_to` when set).
Use `q` / `project_id` / `has_folder` / `due_from` when the office has more
than one page.

## Matching ACCDocs `project_key` / `project_id`

The watch root is typically
`C:\Users\CharlesDossett\DC\ACCDocs\charles@gousis.com\{project_key}\…`.
`project_key` is the Autodesk Desktop Connector folder name, **not** automatically
a CM UUID.

Resolve in this order:

1. **Already-known CM id.** If the agent previously called `GET /api/projects`
   (or an upload returned `project.project_id` / `lead_estimate_id`), pass that
   UUID as `project_id`. That matches `estimates.project_id`,
   `lead_estimates.project_id`, or the lead id itself.
2. **Job / lead number.** Normalize the ACCDocs folder / `project_key` the same
   way ingest already does:
   - `PROJ-2024-0142` → `240142`
   - a string of 6+ digits stays as-is
   Compare to `job_number`, `project_number`, `lead_number`, and `folder_hints`.
3. **Name.** Case-insensitive substring against `project_name`, `lead_name`,
   estimate `name`, and `folder_hints` (ACCDocs display name).
4. **Ambiguous.** If several estimates match the same project, prefer
   `folder_provision_status == "ready"` with a non-empty `folder_path`, then
   `is_current == true`, then newest `updated_at`.

File under `folder_path` only when it is set. Otherwise keep
`C:\usis-cm\data\library\{project_key}` (or skip). Do not synthesize
`Y:\Estimates\{uuid} - …`.

Example:

```
GET /api/ingest/estimates?q=25270&has_folder=1
Authorization: Bearer $CM_API_KEY
```

Due window (last 30 days through future):

```
GET /api/ingest/estimates?due_from=2026-08-21
Authorization: Bearer $CM_API_KEY
```

Cache the map and refresh on a timer or after `POST /api/ingest/events`
`new_project` / `rescan_complete`.
