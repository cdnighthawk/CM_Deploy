# Specialty takeoff enqueue

After an estimate folder is provisioned and the `ready` path is committed, CM
notifies the on-prem specialty-takeoff consumer. The consumer (Ingest Panel)
drops the job for the takeoff bots. CM does not write the office share and
does not write the ingest drop directory.

Public hook: `on_estimate_folder_ready(estimate_id, folder_path)` in
`backend/app/services/specialty_takeoff_enqueue.py`.

`provision_estimate_folder_by_id` calls that hook after
`apply_result_to_estimate` and `session.commit()` (commit first so the
after-commit session is safe), only when `result.status == "ready"` and the
path is non-empty. Provision looks the function up on the module at call time.
Replace it in tests with `monkeypatch`, or install another callable with
`set_on_estimate_folder_ready` (`None` restores the default). Failures are
logged. They never raise into provision and never roll back the estimate.

On Render, folder provision already runs in a daemon thread after the
estimate commit. The follower runs in that same thread, with a short HTTP
timeout, so estimate create stays non-blocking.

There is no `takeoff_jobs` table in CM. The POST is the queue job. The same
body is an upsert: the consumer patches the existing specialty-takeoff job for
`estimate_id` or creates one when none exists. A later folder-provision retry
POSTs again. When `SPECIALTY_TAKEOFF_QUEUE_URL` is unset the hook is a no-op.

## Environment

| Variable | Purpose |
| --- | --- |
| `SPECIALTY_TAKEOFF_QUEUE_URL` | Full URL CM POSTs. Unset = no-op (logged once at info, then debug). |
| `SPECIALTY_TAKEOFF_QUEUE_TOKEN` | Optional. Sent as `X-USIS-Specialty-Takeoff-Token` when set. |
| `SPECIALTY_TAKEOFF_QUEUE_TIMEOUT_SEC` | Optional. Default `5`, max `30`. |
| `SPECIALTY_TAKEOFF_SLUGS` | Optional comma-separated override of the default specialty list. |

Also listed in `backend/.env.example`. Leave the URL unset until the on-prem
consumer is listening. Do not point this at a path CM cannot reach from
Render and expect CM to create directories.

## Path shape

`folder_path` is the absolute path the folder provisioner returned, stored
verbatim. On the data server that is:

```
Y:\Estimates\{job} - {name}
```

Example: `Y:\Estimates\23044 - Turner – Bid Set`.

Canonical artifact root for each specialty, under
`Y:\Estimates\{job} - {name}`:

```
{folder_path}\03_Takeoff\{specialty}\
```

Example: `Y:\Estimates\23044 - Turner – Bid Set\03_Takeoff\doors\`.

The payload `artifact_roots` map has one of those paths per specialty slug.
CM only sends the strings. It does not create the directories.

## Payload (`usis.specialty_takeoff.v1`)

```
POST <SPECIALTY_TAKEOFF_QUEUE_URL>
Content-Type: application/json
X-USIS-Specialty-Takeoff-Token: <token>   # only when the token env is set
```

```json
{
  "schema": "usis.specialty_takeoff.v1",
  "estimate_id": "uuid",
  "folder_path": "Y:\\Estimates\\23044 - Turner – Bid Set",
  "status": "ready_for_takeoff",
  "specialties": [
    "bathroom_partitions",
    "bathroom_accessories",
    "lockers",
    "wall_protection",
    "fire_extinguisher_cabinets",
    "commercial_millwork",
    "doors",
    "markerboards",
    "signage"
  ],
  "artifact_roots": {
    "bathroom_partitions": "Y:\\Estimates\\23044 - Turner – Bid Set\\03_Takeoff\\bathroom_partitions\\",
    "doors": "Y:\\Estimates\\23044 - Turner – Bid Set\\03_Takeoff\\doors\\",
    "signage": "Y:\\Estimates\\23044 - Turner – Bid Set\\03_Takeoff\\signage\\"
  }
}
```

`artifact_roots` includes every slug in `specialties`. Each value is
`{folder_path}\03_Takeoff\{specialty}\`. `status` is `ready_for_takeoff`.

`status` is always `ready_for_takeoff` on this follower. HTTP 4xx/5xx,
timeouts, and client errors are logged. Provision status stays `ready`.

## Specialty slugs

Default list is `SPECIALTY_SLUGS` in
`backend/app/services/specialty_takeoff_enqueue.py`.

| Slug | CSI (estimating presets) |
| --- | --- |
| `bathroom_partitions` | 10 21 00 Compartments and Cubicles |
| `bathroom_accessories` | 10 28 00 Toilet, Bath, and Laundry Accessories |
| `lockers` | 10 51 00 Lockers |
| `wall_protection` | 10 26 00 Wall and Door Protection |
| `fire_extinguisher_cabinets` | 10 44 00 Fire Protection Specialties |
| `commercial_millwork` | 06 40 00 Architectural Woodwork |
| `doors` | 08 11 00 Steel Doors and Frames (also 08 14 / 08 71) |
| `markerboards` | 10 11 00 Visual Display Surfaces |
| `signage` | 10 14 00 Signage |

`signage` is the ninth slug. It is the extra specialty section in the USIS
estimating presets (`USIS_CRM` `estimating-agent/config/preset_spec_sections.json`)
next to the eight product lines above. Furniture (division 12) is not a
specialty takeoff slug. Cubicle curtains stay under `bathroom_partitions`
(10 21). Override the tuple later with `SPECIALTY_TAKEOFF_SLUGS` or by
editing that one constant.
