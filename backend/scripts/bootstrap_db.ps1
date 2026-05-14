# Bootstrap the PostgreSQL role and database for USIS CM.
#
# Reads credentials from backend\.env, then runs scripts\bootstrap_db.sql
# as the `postgres` superuser. Re-runnable: existing role gets its password
# refreshed, existing database is left alone.
#
# Usage (from backend\):
#   powershell -ExecutionPolicy Bypass -File scripts\bootstrap_db.ps1
#
# Requires: psql.exe on PATH. If it isn't, edit $PsqlExe below or add
#   C:\Program Files\PostgreSQL\18\bin to your PATH.

[CmdletBinding()]
param(
    [string]$EnvFile = (Join-Path $PSScriptRoot '..\.env'),
    [string]$SqlFile = (Join-Path $PSScriptRoot 'bootstrap_db.sql'),
    [string]$PsqlExe = 'psql'
)

$ErrorActionPreference = 'Stop'

if (-not (Test-Path $EnvFile)) {
    throw "Missing .env file at $EnvFile. Copy .env.example to .env and fill in values first."
}

# Load KEY=VALUE pairs from .env (ignores comments and blanks).
$envValues = @{}
Get-Content $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith('#') -and $line.Contains('=')) {
        $idx = $line.IndexOf('=')
        $key = $line.Substring(0, $idx).Trim()
        $val = $line.Substring($idx + 1).Trim()
        if ($val.StartsWith('"') -and $val.EndsWith('"')) {
            $val = $val.Substring(1, $val.Length - 2)
        }
        $envValues[$key] = $val
    }
}

function Get-Required([string]$Name) {
    if (-not $envValues.ContainsKey($Name) -or -not $envValues[$Name]) {
        throw "Required key '$Name' missing or blank in $EnvFile"
    }
    return $envValues[$Name]
}

$superPw   = Get-Required 'POSTGRES_SUPERUSER_PASSWORD'
$appPw     = Get-Required 'USIS_APP_DB_PASSWORD'
$dbName    = if ($envValues.ContainsKey('USIS_DB_NAME'))   { $envValues['USIS_DB_NAME'] }   else { 'usis_cm' }
$appRole   = if ($envValues.ContainsKey('USIS_APP_ROLE'))  { $envValues['USIS_APP_ROLE'] }  else { 'usis_app' }
$pgHost    = if ($envValues.ContainsKey('POSTGRES_HOST'))  { $envValues['POSTGRES_HOST'] }  else { 'localhost' }
$pgPort    = if ($envValues.ContainsKey('POSTGRES_PORT'))  { $envValues['POSTGRES_PORT'] }  else { '5432' }

Write-Host "Bootstrapping PostgreSQL:" -ForegroundColor Cyan
Write-Host "  host    : $pgHost`:$pgPort"
Write-Host "  db      : $dbName"
Write-Host "  app role: $appRole"
Write-Host ""

$env:PGPASSWORD = $superPw
try {
    & $PsqlExe `
        -U postgres `
        -h $pgHost `
        -p $pgPort `
        -d postgres `
        -v ON_ERROR_STOP=1 `
        -v usis_db=$dbName `
        -v usis_role=$appRole `
        -v usis_pw=$appPw `
        -f $SqlFile
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
}

if ($code -ne 0) {
    throw "psql exited with code $code. See output above."
}

Write-Host ""
Write-Host "OK. Now run from the backend folder:" -ForegroundColor Green
Write-Host "    flask db upgrade"
