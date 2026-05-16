# USIS CM — operator runbook

## Start / stop (development)

```powershell
cd E:\programs\USIS_CM\backend
.\.venv\Scripts\Activate.ps1
flask run --host 127.0.0.1 --port 5000
```

## Start (production pattern)

Use a production WSGI server (e.g. waitress or gunicorn) in front of HTTPS termination, not `flask run`.

```powershell
waitress-serve --listen=127.0.0.1:5000 app:create_app
```

## Health

- `GET /healthz` — returns JSON including `request_id` and a cheap DB probe.
- All API responses echo `X-Request-Id` (also generated if the client omits `X-Request-Id`).

## Migrations

```powershell
flask db upgrade
```

## Upload storage

Binary uploads land under Flask `instance/` by default unless overridden:

| Feature | Env override | Default folder |
|---------|----------------|-----------------|
| Drawings | `DRAWING_UPLOAD_FOLDER` | `instance/drawing_uploads` |
| Spec section PDFs | `SPEC_SECTION_UPLOAD_FOLDER` | `instance/spec_section_uploads` |
| RFI attachments | `RFI_ATTACHMENT_UPLOAD_FOLDER` | `instance/rfi_attachment_uploads` |

Include these paths in filesystem backups alongside PostgreSQL.

## Smoke test

From `backend\`, run `powershell -ExecutionPolicy Bypass -File scripts\smoke.ps1` after deploy or local changes.

## Database backup

Run `scripts\backup_usis_cm.ps1` (edit `DATABASE_URL` / output path inside the script or pass parameters as documented there).

## Push local database to Render

One-time (or repeatable) data migration from dev Postgres to Render production:

1. Set `RENDER_DATABASE_URL` to the **External** connection string from Render Dashboard → `usis-cm-db` → Connect.
2. From `backend\`: `powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1 -ConnectivityOnly`
3. Then run without `-ConnectivityOnly` to backup Render, dump local data, and restore.

Full procedure, encryption keys, and instance file caveats: [docs/migrate-local-db-to-render.md](../docs/migrate-local-db-to-render.md).
