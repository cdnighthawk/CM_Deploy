# USIS CM - dev setup for backend + mobile
# Run from repo root:  .\scripts\setup-mobile-dev.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host "==> Backend: venv + migration" -ForegroundColor Cyan
Push-Location "$Root\backend"
if (-not (Test-Path ".\.venv\Scripts\Activate.ps1")) {
    python -m venv .venv
}
.\.venv\Scripts\Activate.ps1
pip install -q -r requirements.txt
$env:FLASK_APP = "app:create_app"
flask db upgrade
Pop-Location

Write-Host "==> Mobile: .env + npm" -ForegroundColor Cyan
Push-Location "$Root\mobile"
if (-not (Test-Path ".\.env")) {
    Copy-Item ".\.env.example" ".\.env"
    Write-Host "Created mobile\.env - edit EXPO_PUBLIC_API_BASE for your device." -ForegroundColor Yellow
}
if (-not (Test-Path ".\node_modules")) {
    npm install
}
Pop-Location

Write-Host "==> Gulp: rebuild static shell" -ForegroundColor Cyan
Push-Location "$Root\W3CRM-v3.0-13_September_2025\gulp"
if (-not (Test-Path ".\node_modules")) {
    npm ci
}
npx gulp build
Pop-Location

Write-Host ""
Write-Host "Done. Next:" -ForegroundColor Green
Write-Host "  Backend: cd backend; .\.venv\Scripts\Activate.ps1; flask run --host 0.0.0.0 --port 5000"
Write-Host "  Mobile:  cd mobile; npm start"
Write-Host "  Android emulator: EXPO_PUBLIC_API_BASE=http://10.0.2.2:5000"
Write-Host "  Phone on LAN:     EXPO_PUBLIC_API_BASE=http://YOUR_PC_IP:5000"
