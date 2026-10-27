# Start the FastAPI backend (issues LiveKit join tokens).
#
#   .\scripts\start-backend.ps1
#
# Binds 0.0.0.0 so the second machine can reach the API over the LAN.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, which turns Vietnamese diacritics into mojibake.

$ErrorActionPreference = "Stop"

$root    = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "backend"
$python  = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "No virtualenv found. Run first:  cd backend; python -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.txt"
}

$envFile = Join-Path $backend ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $backend ".env.example") $envFile
    Write-Host "Created backend/.env from the example file." -ForegroundColor Yellow
}

Push-Location $backend
try {
    & $python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
} finally {
    Pop-Location
}
