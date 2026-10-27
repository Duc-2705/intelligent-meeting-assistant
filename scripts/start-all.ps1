# Open all three services, one PowerShell window each.
#
#   .\scripts\start-all.ps1                      # auto: Tailscale, else LAN
#   .\scripts\start-all.ps1 -Network Tailscale
#   .\scripts\start-all.ps1 -Network Lan
#
# The LiveKit window prints "node_ip : <ip>". Use that IP for the second
# machine. On the Tailscale path the backend detects it automatically; on the
# LAN path you must also set LIVEKIT_URL in backend/.env.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, which turns Vietnamese diacritics into mojibake.

param(
    [ValidateSet("Auto", "Tailscale", "Lan")]
    [string]$Network = "Auto"
)

$ErrorActionPreference = "Stop"

$root    = Split-Path -Parent $PSScriptRoot
$scripts = Join-Path $root "scripts"

function Start-ServiceWindow {
    param([string]$Name, [string]$ScriptPath, [string]$Arguments = "")
    Write-Host "Opening window: $Name" -ForegroundColor Cyan
    Start-Process powershell -ArgumentList @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-Command",
        "`$host.UI.RawUI.WindowTitle = '$Name'; & '$ScriptPath' $Arguments"
    )
}

Start-ServiceWindow -Name "LiveKit"  -ScriptPath (Join-Path $scripts "start-livekit.ps1") -Arguments "-Network $Network"
Start-Sleep -Seconds 3
Start-ServiceWindow -Name "Backend"  -ScriptPath (Join-Path $scripts "start-backend.ps1")
Start-Sleep -Seconds 2
Start-ServiceWindow -Name "Frontend" -ScriptPath (Join-Path $scripts "start-frontend.ps1")

Write-Host ""
Write-Host "Three windows opened. Check:" -ForegroundColor Green
Write-Host "  LiveKit  : ws://<lan-ip>:7880"
Write-Host "  Backend  : http://localhost:8000/docs"
Write-Host "  Frontend : http://localhost:5173"
