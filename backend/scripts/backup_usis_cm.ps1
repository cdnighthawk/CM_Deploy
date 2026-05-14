# Example pg_dump wrapper — set PGPASSWORD or use .pgpass before running.
# Usage:  $env:PGPASSWORD='...'; powershell -File scripts\backup_usis_cm.ps1
$ErrorActionPreference = "Stop"
$outDir = if ($env:USIS_BACKUP_DIR) { $env:USIS_BACKUP_DIR } else { Join-Path $PSScriptRoot ".." ".." "backups" }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
$fn = Join-Path $outDir "usis_cm_$stamp.dump"
$db = if ($env:USIS_DB_NAME) { $env:USIS_DB_NAME } else { "usis_cm" }
$pgHost = if ($env:POSTGRES_HOST) { $env:POSTGRES_HOST } else { "127.0.0.1" }
$user = if ($env:POSTGRES_SUPERUSER_USER) { $env:POSTGRES_SUPERUSER_USER } else { "postgres" }
Write-Host "Writing $fn (custom-format pg_dump)..."
& pg_dump -h $pgHost -U $user -Fc -f $fn $db
Write-Host "Done."
