# Run all reference and operations CSV imports in dependency order.
# Prereqs: PostgreSQL up, backend\.env configured, flask db upgrade already applied.
# Optional: set DATABASE_FILES_ROOT to your CSV folder (see .env.example).

$ErrorActionPreference = "Stop"
$BackendRoot = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $BackendRoot ".venv\Scripts\python.exe"))) {
    Write-Error "Python venv not found at $BackendRoot\.venv — run setup from README first."
}
$Python = Join-Path $BackendRoot ".venv\Scripts\python.exe"
Set-Location $BackendRoot

Write-Host "=== load_wage_rates ===" -ForegroundColor Cyan
& $Python scripts\load_wage_rates.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== load_material_pricing (BOBRICK + uPDATED PRICING) ===" -ForegroundColor Cyan
& $Python scripts\load_material_pricing.py --all-defaults
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== load_sales_tax_rates ===" -ForegroundColor Cyan
& $Python scripts\load_sales_tax_rates.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== load_lead_estimates ===" -ForegroundColor Cyan
& $Python scripts\load_lead_estimates.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== load_corecon_transactions ===" -ForegroundColor Cyan
& $Python scripts\load_corecon_transactions.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== load_hubspot_contacts (optional CRM) ===" -ForegroundColor Cyan
& $Python scripts\load_hubspot_contacts.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== link_jobs ===" -ForegroundColor Cyan
& $Python scripts\link_jobs.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "=== healthz ===" -ForegroundColor Cyan
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:5000/healthz" -Method Get
    $h | ConvertTo-Json -Compress
} catch {
    Write-Warning "Flask not reachable on :5000 — start flask run to verify healthz."
}

Write-Host "All import steps finished." -ForegroundColor Green
