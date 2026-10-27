# Start the Vite dev server.
#
#   .\scripts\start-frontend.ps1
#   .\scripts\start-frontend.ps1 -ProxyTarget http://192.168.8.104:8000
#
# -ProxyTarget is for running Vite on the SECOND machine: Vite proxies /api/*
# to the backend on the host machine. That way the second machine still opens
# http://localhost:5173, which is a secure context, so the browser grants
# microphone and camera access without any Chrome flag.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, which turns Vietnamese diacritics into mojibake.

param(
    [string]$ProxyTarget = "",
    [int]$Port = 5173
)

$ErrorActionPreference = "Stop"

$root     = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root "frontend"

if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
    throw "Dependencies not installed. Run first:  cd frontend; npm install"
}

if ($ProxyTarget) {
    $env:VITE_PROXY_TARGET = $ProxyTarget
    Write-Host "Proxying /api/* -> $ProxyTarget" -ForegroundColor Cyan
}
$env:VITE_PORT = "$Port"

Push-Location $frontend
try {
    npm run dev
} finally {
    Pop-Location
}
