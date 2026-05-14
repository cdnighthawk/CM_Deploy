# One-shot local dev setup: Python venv, deps, .env, optional Docker Postgres, Alembic, W3CRM gulp build.
#
# Run from anywhere:
#   powershell -ExecutionPolicy Bypass -File E:\programs\USIS_CM\backend\scripts\setup_dev.ps1
#
# Requires: Python 3.12+ on PATH. Optional: Docker Desktop (for Postgres) or a local PostgreSQL 16+ with matching .env.

$ErrorActionPreference = "Stop"
$BackendRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$RepoRoot = Split-Path $BackendRoot -Parent
$GulpRoot = Join-Path $RepoRoot "W3CRM-v3.0-13_September_2025\gulp"
$DevDbPassword = "USIS_Local_Dev_2026"

Set-Location $BackendRoot
Write-Host "== USIS CM dev setup ==" -ForegroundColor Cyan
Write-Host "Backend: $BackendRoot"

# Docker Desktop often installs here without adding docker.exe to user PATH.
$dockerBin = "C:\Program Files\Docker\Docker\resources\bin"
if (Test-Path (Join-Path $dockerBin "docker.exe")) {
    $env:PATH = $dockerBin + [IO.Path]::PathSeparator + $env:PATH
}

# --- Python venv + pip ---
$venvPy = Join-Path $BackendRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
    Write-Host "Creating .venv ..." -ForegroundColor Yellow
    & python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "python -m venv failed. Install Python 3.12+." }
}
Write-Host "Installing Python dependencies ..." -ForegroundColor Yellow
& $venvPy -m pip install --upgrade pip -q
& $venvPy -m pip install -r (Join-Path $BackendRoot "requirements.txt")

# --- .env ---
$envPath = Join-Path $BackendRoot ".env"
if (-not (Test-Path $envPath)) {
    Write-Host "Creating .env (local dev defaults; not for production) ..." -ForegroundColor Yellow
    $secret = [Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Maximum 256 }))
    $dbUrl = "postgresql+psycopg://usis_app:${DevDbPassword}@127.0.0.1:5432/usis_cm"
    # Here-string terminator ("@) must be at column 0; see about_Strings.
    @"
FLASK_APP=app:create_app
FLASK_ENV=development
SECRET_KEY=$secret

DATABASE_URL=$dbUrl

CORS_ORIGINS=http://127.0.0.1:3000,http://localhost:3000,http://127.0.0.1:5000,http://localhost:5000,http://127.0.0.1:5500,http://localhost:5500

POSTGRES_SUPERUSER_PASSWORD=$DevDbPassword
USIS_APP_DB_PASSWORD=$DevDbPassword
POSTGRES_SUPERUSER_USER=postgres
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
USIS_DB_NAME=usis_cm
USIS_APP_ROLE=usis_app

# Optional: BuildingConnected CSV path - Flask imports on startup when lead_estimates is empty (development).
# BC_PROJECTS_CSV=
"@ | Set-Content -Path $envPath -Encoding utf8
    Write-Host "Wrote $envPath" -ForegroundColor Green
} else {
    Write-Host ".env already exists - leaving as-is." -ForegroundColor DarkGray
}

# --- Docker Postgres (optional) ---
$compose = Join-Path $BackendRoot "docker-compose.yml"
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    Write-Host "Starting PostgreSQL via Docker ..." -ForegroundColor Yellow
    Push-Location $BackendRoot
    try {
        & docker compose up -d 2>&1 | Write-Host
        Write-Host "Waiting for Postgres healthcheck ..." -ForegroundColor Yellow
        Start-Sleep -Seconds 8
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Docker not on PATH - skipping 'docker compose up'." -ForegroundColor Yellow
    Write-Host "  Install Docker Desktop, then from backend run:  docker compose up -d" -ForegroundColor DarkYellow
    Write-Host "  Or install PostgreSQL and run scripts\bootstrap_db.ps1 with a real superuser password in .env" -ForegroundColor DarkYellow
}

# --- Alembic ---
$flaskExe = Join-Path $BackendRoot ".venv\Scripts\flask.exe"
$env:FLASK_APP = "app:create_app"
Push-Location $BackendRoot
try {
    Write-Host "Running database migrations (flask db upgrade) ..." -ForegroundColor Yellow
    & $flaskExe db upgrade 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "flask db upgrade failed (database may be down). Start Postgres then re-run:" -ForegroundColor Red
        Write-Host "  cd $BackendRoot" -ForegroundColor Red
        Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Red
        Write-Host "  flask db upgrade" -ForegroundColor Red
    }
} catch {
    Write-Host $_ -ForegroundColor Red
} finally {
    Pop-Location
}

# --- W3CRM gulp build ---
if (Test-Path $GulpRoot) {
    Write-Host "Building W3CRM theme (gulp build) ..." -ForegroundColor Yellow
    Push-Location $GulpRoot
    try {
        if (-not (Test-Path "node_modules")) {
            npm install --no-fund --no-audit 2>&1 | Write-Host
        }
        npx gulp build 2>&1 | Write-Host
        Write-Host "W3CRM dist: $(Join-Path $GulpRoot 'dist')" -ForegroundColor Green
    } catch {
        Write-Host $_ -ForegroundColor Red
    } finally {
        Pop-Location
    }
}
else {
    Write-Host "W3CRM gulp folder not found at $GulpRoot - skipping theme build." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Cyan
Write-Host ('  1) API:  cd ' + $BackendRoot + ' ; .\.venv\Scripts\Activate.ps1 ; flask run') -ForegroundColor White
Write-Host '  2) UI:   open dist\construction\leads.html in browser, or: npx gulp (dev server) from gulp folder' -ForegroundColor White
Write-Host '  3) If API/CORS errors: add your Live Server origin to CORS_ORIGINS in .env' -ForegroundColor White
