# Run API tests using the backend virtualenv (avoids system Python missing psycopg / wrong deps).
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent $here
Set-Location $root
$pytest = Join-Path $root '.venv\Scripts\pytest.exe'
if (-not (Test-Path $pytest)) {
    Write-Error "Missing $pytest - create the venv and run pip install -r requirements.txt in backend."
}
& $pytest @args
