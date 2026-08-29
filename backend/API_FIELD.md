# FinishWorks Field API

Shared contract for the native Android field app (`FinishWorksField`) and the Expo client in `mobile/`. Website login (`POST /auth/login`, session cookie) is **not** used by field apps.

Android chrome uses the website tokens from `usis-ui.css`: primary `#1F4E5F`, paper `#FFFFFF`, page `#F4F6F8`.

**Production base:** `https://www.usiscm.com`  
**Local / emulator:** `http://10.0.2.2:5000` (Android emulator) or `http://<LAN-IP>:5000` (device)

All field routes are under `/api/v1` unless noted. Send `Authorization: Bearer <access_token>`, `Accept: application/json`, and `X-Request-Id`. On **401**, refresh once; if refresh fails, wipe tokens, keep cached reads, and block writes.

Offline: last-write-wins on daily-report **section keys**. Never drop a photo — queue and retry.

---

## Auth

| Method | Path | Body | Success |
|--------|------|------|---------|
| POST | `/api/v1/auth/mobile/login` | `{email, password, device_label?}` | tokens + user |
| POST | `/api/v1/auth/mobile/refresh` | `{refresh_token}` | new tokens (old refresh revoked) |
| POST | `/api/v1/auth/mobile/logout` | `{refresh_token}` | `{ok: true}` |

Login / refresh **200**:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque>",
  "expires_in": 3600,
  "token_type": "Bearer",
  "user": { "id": "<uuid>", "email": "...", "first_name": "...", "last_name": "..." }
}
```

Errors: `401 {"error":"invalid email or password"}` / `invalid or expired refresh token`.

`GET /api/v1/me` → `{item, capabilities, entity: "session_user"}`.

There is **no** FCM / device-token endpoint. Android stubs registration.

---

## Projects

`GET /api/v1/projects?limit=500`

```json
{
  "items": [
    {
      "id": "<uuid>",
      "number": "26-104",
      "name": "Job name",
      "city": "Phoenix",
      "state": "AZ",
      "status": "active",
      "project_type": "commercial",
      "updated_at": "<iso>",
      "latitude": 33.44,
      "longitude": -112.07,
      "geofence_radius_m": 250
    }
  ],
  "total": 1,
  "entity": "projects",
  "project_scope": "all"
}
```

---

## Drawings

`GET /api/v1/projects/:id/drawings` — one row per sheet (`series_id`). Query: `q`, `discipline`, `drawing_set`, `limit`, `offset`.

Each item:

- `series_id`, `sheet_number`, `sheet_title`, `discipline`, `drawing_set`, `revision_count`
- `current_revision` — newest; treat this as **current**. Never present a superseded revision as current without a banner.
- `revisions[]` — newest first; same shape as `_drawing_public`

Revision / file:

- `GET /api/v1/drawings/:id/revisions`
- `GET /api/v1/drawings/:id/file` — raw PDF (`Authorization` required). `file_url` is usually `/api/v1/drawings/:id/file` (relative).

### Markup

`GET/POST /api/v1/drawings/:id/annotations`  
`PATCH/DELETE /api/v1/drawing-annotations/:id`

`type`: `measurement` | `user_note` | `ai_review` | `cloud` | `arrow` | `highlight` | `text_note` | `photo_pin`

Field markup `data` (suggested):

```json
{
  "kind": "cloud",
  "page": 0,
  "points": [{"x": 0.12, "y": 0.34}],
  "color": "#E11D48",
  "text": "",
  "photo_id": null
}
```

`photo_pin` may set `photo_id` after upload.

---

## Submittals

**List / detail (field viewer):**

- `GET /api/v1/projects/:id/submittals`
- `GET /api/v1/projects/:id/submittals/:sid`

Snake_case item: `id`, `number` (int or string), `title`, `spec_section`, `status`, `ball_in_court`, `current_attachment.file_url`, `attachments[]`, `audit[]`, `permissions`.

v1 detail often omits `revision.id` and `permissions.canAct`. Field apps then GET `/api/submittals/:sid` (QC detail) for those fields.

PDF: `GET /api/v1/documents/:id/file` (or attachment `file_url`).

**Comment / approve / reject (QC — do not invent PATCH-status as the action):**

- `PATCH /api/submittals/:id/revisions/:rev/checklist` — `{items:[{id, result, comment}]}` or a custom item `{label, source: "custom", comment}` (field comment)
- `POST /api/submittals/:id/revisions/:rev/stamp` — `{stamp, comments?}`

Stamps: `no_exceptions` | `make_corrections_noted` | `revise_resubmit` | `rejected` | `for_info_only`.

v1 field actions: view always; comment when a revision id is present; stamp when QC `permissions.canAct` or `can_edit` is true. Queue writes while offline.

---

## Daily reports (field)

One report per project per calendar date. Opening “today” **gets or creates** a draft.

| Method | Path |
|--------|------|
| GET | `/api/v1/projects/:id/daily-reports?date=YYYY-MM-DD` |
| PUT | `/api/v1/daily-reports/:id` |

**Item:**

```json
{
  "id": "<uuid>",
  "project_id": "<uuid>",
  "date": "2026-08-28",
  "status": "draft",
  "sections": {
    "weather": {"conditions": "", "temp_f": null, "notes": ""},
    "manpower": [],
    "equipment": [],
    "deliveries": [],
    "work_performed": "",
    "delays": "",
    "photos": [],
    "notes": ""
  },
  "updated_at": "<iso>",
  "completed_at": null
}
```

`PUT` body: `{sections?: object, status?: "draft"|"complete"}`.  
Server merges **top-level section keys** (last write wins per key). `status: complete` locks further field edits (admin / superuser can still edit).

---

## Photos (field)

| Method | Path |
|--------|------|
| GET | `/api/v1/projects/:id/photos` |
| POST | `/api/v1/projects/:id/photos` (multipart) |
| PATCH | `/api/v1/photos/:id` `{caption?, location_text?, drawing_id?, daily_report_id?}` |
| GET | `/api/v1/photos/:id/file` |

`POST` form fields: `file` (required), `taken_at`, `lat`, `lon`, `caption`, `location_text`, `drawing_id`, `daily_report_id`.

**Item:**

```json
{
  "id": "<uuid>",
  "project_id": "<uuid>",
  "file_url": "/api/v1/photos/<uuid>/file",
  "taken_at": "<iso>",
  "lat": 33.44,
  "lon": -112.07,
  "caption": "",
  "location_text": "Level 2 corridor",
  "drawing_id": null,
  "daily_report_id": null,
  "created_at": "<iso>"
}
```

Compress on device before upload (max edge 2560px, JPEG ~0.72). Retry with WorkManager; never block the shutter on network.

---

## Time clock (field)

Self clock-in/out with GPS, optional punch photo, breaks, and mid-day job/cost-code switch. One open entry per user. `client_id` is a device-generated UUID; replaying it returns the existing row.

| Method | Path |
|--------|------|
| GET | `/api/v1/time-clock/me` |
| POST | `/api/v1/time-clock/clock-in` |
| POST | `/api/v1/time-clock/clock-out` |
| POST | `/api/v1/time-clock/break-start` |
| POST | `/api/v1/time-clock/break-end` |
| POST | `/api/v1/time-clock/switch` |
| GET | `/api/v1/projects/:id/cost-codes` |

Clock-in / clock-out / switch body:

```json
{
  "project_id": "<uuid>",
  "entry_id": "<uuid or client_id>",
  "cost_code_id": "<uuid or null>",
  "occurred_at": "<iso>",
  "lat": 33.44,
  "lon": -112.07,
  "accuracy_m": 12.5,
  "note": "",
  "client_id": "<uuid>",
  "new_entry_client_id": "<uuid>",
  "photo_id": "<uuid or null>",
  "override_geofence": false
}
```

`cost_code_id` is required when the project has any active cost codes.
If the project has `latitude`/`longitude` and the punch is outside `geofence_radius_m`, the server returns **409** unless `override_geofence` is true (`geofence_ok` is then stored as false).

`GET /time-clock/me` → `{open, today[], items[]}` for the last 7 days. Each entry includes `punches[]` and `paid_seconds` (shift length minus breaks).

---

## iOS / Expo parity

Use these JSON shapes. Do not introduce a second payload. Expo today calls auth, projects, and drawings only; Android also uses submittals + the new daily-report and photo routes.
