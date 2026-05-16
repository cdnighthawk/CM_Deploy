# Push local PostgreSQL data to Render (USIS CM).
#
# Assumes Render already ran ``flask db upgrade`` (empty schema). Dumps DATA ONLY
# from local and restores into Render. Backs up Render first.
#
# Prerequisites:
#   - pg_dump.exe and pg_restore.exe on PATH (PostgreSQL client tools)
#   - Render External Database URL from Dashboard → usis-cm-db → Connect → External
#
# Environment (set in the shell; never commit these):
#   LOCAL_DATABASE_URL   — optional; defaults to DATABASE_URL from backend\.env
#   RENDER_DATABASE_URL  — required (Render external connection string)
#
# Usage (from backend\):
#   $env:RENDER_DATABASE_URL = "postgresql://usis_app:...@...render.com/usis_cm"
#   powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1
#
#   # Test connections only:
#   powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1 -ConnectivityOnly
#
#   # If Render has stray rows (bootstrap admin, failed prior restore):
#   powershell -ExecutionPolicy Bypass -File scripts\push_db_to_render.ps1 -TruncateRenderBeforeRestore
#
# See docs/migrate-local-db-to-render.md for full procedure, secrets, and instance files.

[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '..\.env'),
    [string]$LocalDatabaseUrl = $env:LOCAL_DATABASE_URL,
    [string]$RenderDatabaseUrl = $env:RENDER_DATABASE_URL,
    [string]$BackupDir = $env:USIS_BACKUP_DIR,
    [switch]$ConnectivityOnly,
    [switch]$SkipRenderBackup,
    [switch]$TruncateRenderBeforeRestore,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Import-DotEnv([string]$Path) {
    $values = @{}
    if (-not (Test-Path $Path)) { return $values }
    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
            $idx = $line.IndexOf('=')
            $key = $line.Substring(0, $idx).Trim()
            $val = $line.Substring($idx + 1).Trim()
            if ($val.StartsWith('"') -and $val.EndsWith('"')) {
                $val = $val.Substring(1, $val.Length - 2)
            }
            $values[$key] = $val
        }
    }
    return $values
}

function ConvertTo-LibpqUri([string]$DatabaseUrl) {
    if (-not $DatabaseUrl) { throw "Database URL is empty." }
    $u = $DatabaseUrl.Trim()
    if ($u -match '^postgresql\+psycopg://') {
        $u = 'postgresql://' + $u.Substring('postgresql+psycopg://'.Length)
    }
    elseif ($u -match '^postgres://') {
        $u = 'postgresql://' + $u.Substring('postgres://'.Length)
    }
    elseif ($u -notmatch '^postgresql://') {
        throw "Unsupported DATABASE_URL scheme (expected postgresql:// or postgres://): $($u.Substring(0, [Math]::Min(40, $u.Length)))..."
    }
    return $u
}

function Get-UriHostDisplay([string]$Uri) {
    try {
        $parsed = [Uri]$Uri
        return "$($parsed.Host):$($parsed.Port)/$($parsed.AbsolutePath.TrimStart('/'))"
    }
    catch {
        return "(could not parse URI)"
    }
}

function Assert-PgTool([string]$Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $cmd) {
        throw "$Name not found on PATH. Install PostgreSQL client tools and add their bin folder to PATH."
    }
    return $cmd.Source
}

function Invoke-Psql([string]$DbUri, [string]$Sql) {
    & psql $DbUri -v ON_ERROR_STOP=1 -q -c $Sql
    if ($LASTEXITCODE -ne 0) {
        throw "psql failed (exit $LASTEXITCODE)."
    }
}

function Test-DatabaseConnection([string]$Label, [string]$DbUri) {
    Write-Host "  $Label : $(Get-UriHostDisplay $DbUri)"
    $version = & psql $DbUri -v ON_ERROR_STOP=1 -Atqc "SELECT version();"
    if ($LASTEXITCODE -ne 0) { throw "Cannot connect to $Label." }
    Write-Host "    server: $($version.Trim())" -ForegroundColor DarkGray
    $alembic = & psql $DbUri -v ON_ERROR_STOP=1 -Atqc "SELECT version_num FROM alembic_version LIMIT 1;"
    if ($LASTEXITCODE -eq 0 -and $alembic) {
        Write-Host "    alembic_version: $($alembic.Trim())" -ForegroundColor DarkGray
    }
    else {
        Write-Host "    alembic_version: (missing - run flask db upgrade on this database first)" -ForegroundColor Yellow
    }
}

function Invoke-TruncatePublicTables([string]$DbUri) {
    Write-Step "Truncating all public tables on Render (CASCADE)"
    $sql = @"
DO `$`$ DECLARE r RECORD;
BEGIN
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
    EXECUTE 'TRUNCATE TABLE ' || quote_ident(r.tablename) || ' CASCADE';
  END LOOP;
END `$`$;
"@
    if ($DryRun) {
        Write-Host "[DryRun] Would run TRUNCATE ... CASCADE on public.*"
        return
    }
    Invoke-Psql -DbUri $DbUri -Sql $sql
    Write-Host "    Render public schema truncated." -ForegroundColor Green
}

# --- Resolve URLs ---
$dotenv = Import-DotEnv -Path $EnvFile
if (-not $LocalDatabaseUrl -and $dotenv.ContainsKey('DATABASE_URL')) {
    $LocalDatabaseUrl = $dotenv['DATABASE_URL']
}
if (-not $LocalDatabaseUrl) {
    throw "Set LOCAL_DATABASE_URL or DATABASE_URL in $EnvFile"
}
if (-not $RenderDatabaseUrl) {
    throw @"
RENDER_DATABASE_URL is not set.

Copy the External connection string from Render Dashboard:
  usis-cm-db → Connect → External Database URL

Then in PowerShell:
  `$env:RENDER_DATABASE_URL = 'postgresql://usis_app:...@....render.com/usis_cm'
"@
}

$localUri = ConvertTo-LibpqUri $LocalDatabaseUrl
$renderUri = ConvertTo-LibpqUri $RenderDatabaseUrl

Assert-PgTool 'pg_dump' | Out-Null
Assert-PgTool 'pg_restore' | Out-Null
Assert-PgTool 'psql' | Out-Null

if (-not $BackupDir) {
    $BackupDir = Join-Path $PSScriptRoot '..' '..' 'backups'
}
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null

Write-Step "Connectivity check"
Test-DatabaseConnection -Label 'Local' -DbUri $localUri
Test-DatabaseConnection -Label 'Render' -DbUri $renderUri

if ($localUri -eq $renderUri) {
    throw "LOCAL and RENDER database URLs are identical - refusing to run."
}

if ($ConnectivityOnly) {
    Write-Host ""
    Write-Host "Connectivity OK. No dump/restore performed (-ConnectivityOnly)." -ForegroundColor Green
    exit 0
}

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$renderBackup = Join-Path $BackupDir "render_usis_cm_before_push_$stamp.dump"
$dataDump = Join-Path $BackupDir "local_usis_cm_data_only_$stamp.dump"

if (-not $SkipRenderBackup) {
    Write-Step "Backing up Render database → $renderBackup"
    if ($DryRun) {
        Write-Host "[DryRun] pg_dump -Fc ... $renderBackup"
    }
    else {
        & pg_dump --dbname=$renderUri --format=custom --no-owner --no-acl --file=$renderBackup
        if ($LASTEXITCODE -ne 0) { throw "Render backup (pg_dump) failed." }
        Write-Host "    Render backup saved." -ForegroundColor Green
    }
}
else {
    Write-Host "Skipping Render backup (-SkipRenderBackup)." -ForegroundColor Yellow
}

Write-Step "Dumping local data only → $dataDump"
if ($DryRun) {
    Write-Host "[DryRun] pg_dump --data-only -Fc ... $dataDump"
}
else {
    & pg_dump --dbname=$localUri --format=custom --data-only --no-owner --no-acl --file=$dataDump
    if ($LASTEXITCODE -ne 0) { throw "Local data dump (pg_dump) failed." }
    Write-Host "    Local data dump saved." -ForegroundColor Green
}

if ($TruncateRenderBeforeRestore) {
    Invoke-TruncatePublicTables -DbUri $renderUri
}

Write-Step "Restoring local data into Render"
if ($DryRun) {
    Write-Host "[DryRun] pg_restore --data-only --disable-triggers ..."
    exit 0
}

& pg_restore `
    --dbname=$renderUri `
    --data-only `
    --disable-triggers `
    --no-owner `
    --no-acl `
    --verbose `
    $dataDump

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "pg_restore reported errors (exit $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "Common fixes:" -ForegroundColor Yellow
    Write-Host "  - Re-run with -TruncateRenderBeforeRestore if Render already had rows."
    Write-Host "  - Ensure both DBs ran the same migrations (compare alembic_version above)."
    Write-Host "  - Restore Render from backup: pg_restore --dbname=`$env:RENDER_DATABASE_URL $renderBackup"
    exit $LASTEXITCODE
}

Write-Step "Verifying row counts (sample tables)"
$tables = @('users', 'projects', 'lead_estimates')
foreach ($t in $tables) {
    $exists = & psql $renderUri -v ON_ERROR_STOP=0 -Atqc "SELECT to_regclass('public.$t') IS NOT NULL;"
    if ($exists -ne 't') { continue }
    $cnt = & psql $renderUri -v ON_ERROR_STOP=1 -Atqc "SELECT COUNT(*) FROM public.$t;"
    Write-Host "    $t : $($cnt.Trim()) rows"
}

Write-Host ""
Write-Host "Done. Next steps:" -ForegroundColor Green
Write-Host "  1. Copy TOKEN_ENCRYPTION_KEY and SECRET_KEY from local .env to Render if you use I-9/W-4/BC encrypted fields."
Write-Host "  2. Log in at your Render URL /page-login.html with your local user email/password."
Write-Host "  3. Upload binary files separately (backend/instance is not in this dump)."
Write-Host "  See docs/migrate-local-db-to-render.md"
