# Quick post-deploy smoke: healthz + optional RFI list (requires PROJECT_ID env).
$ErrorActionPreference = "Stop"
$base = if ($env:USIS_API_BASE) { $env:USIS_API_BASE.TrimEnd("/") } else { "http://127.0.0.1:5000" }

Write-Host "GET $base/healthz"
$r = Invoke-WebRequest -Uri "$base/healthz" -UseBasicParsing
Write-Host "Status:" $r.StatusCode
Write-Host $r.Content

if ($env:PROJECT_ID) {
    $projectId = $env:PROJECT_ID.Trim()
    Write-Host "`nGET $base/api/v1/projects/$projectId/rfis?limit=5"
    $r2 = Invoke-WebRequest -Uri "$base/api/v1/projects/$projectId/rfis?limit=5" -UseBasicParsing
    Write-Host "Status:" $r2.StatusCode
    Write-Host $r2.Content.Substring(0, [Math]::Min(500, $r2.Content.Length))
}
