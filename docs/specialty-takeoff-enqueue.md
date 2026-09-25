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
    "lockers",
    "concrete",
    "door_spec",
    "room_interiors",
    "wall_protection",
    "partitions",
    "fec",
    "millwork",
    "bathroom_accessories"
  ],
  "artifact_roots": {
    "lockers": "Y:\\Estimates\\23044 - Turner – Bid Set\\03_Takeoff\\lockers\\",
    "partitions": "Y:\\Estimates\\23044 - Turner – Bid Set\\03_Takeoff\\partitions\\",
    "fec": "Y:\\Estimates\\23044 - Turner – Bid Set\\03_Takeoff\\fec\\"
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

| Slug | CSI / scope |
| --- | --- |
| `lockers` | CSI 10 51 00 |
| `concrete` | Div 03 + excav / Div 32 |
| `door_spec` | Div 8 DFH |
| `room_interiors` | room inside-face rings |
| `wall_protection` | CSI 10 26 00 |
| `partitions` | CSI 10 21 13 |
| `fec` | CSI 10 44 16 |
| `millwork` | CSI 06 40 / 06 41 |
| `bathroom_accessories` | CSI 10 28 13 |

These nine strings are the contract. Do not substitute other product names.
`SPECIALTY_TAKEOFF_SLUGS` can replace the tuple later without editing call sites.
