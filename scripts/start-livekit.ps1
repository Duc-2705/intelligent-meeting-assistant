# Start the LiveKit server with node_ip set to an address the second machine
# can actually reach.
#
#   .\scripts\start-livekit.ps1                  # auto: Tailscale, else LAN
#   .\scripts\start-livekit.ps1 -Network Lan     # force Wi-Fi / LAN address
#   .\scripts\start-livekit.ps1 -NodeIp 10.11.202.18
#
# Why node_ip matters: LiveKit advertises ICE candidates to clients. If node_ip
# is 127.0.0.1 or the wrong interface, the second machine still "joins" the
# room but no media can flow -> no audio, no video.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, which turns Vietnamese diacritics into mojibake.

param(
    [string]$NodeIp = "",
    [ValidateSet("Auto", "Tailscale", "Lan")]
    [string]$Network = "Auto"
)

$ErrorActionPreference = "Stop"

$root       = Split-Path -Parent $PSScriptRoot
$livekitDir = Join-Path $root "livekit"
$exe        = Join-Path $livekitDir "livekit-server.exe"
$template   = Join-Path $livekitDir "livekit.yaml.example"

if (-not (Test-Path $exe)) {
    throw "Cannot find livekit-server.exe at $exe"
}

function Get-TailscaleIP {
    $cli = Get-Command tailscale -ErrorAction SilentlyContinue
    if ($cli) {
        $ip = & tailscale ip -4 2>$null | Select-Object -First 1
        if ($ip) { return $ip.Trim() }
    }
    $addr = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.InterfaceAlias -like "*Tailscale*" } |
            Select-Object -First 1
    if ($addr) { return $addr.IPAddress }
    return $null
}

function Get-LanIP {
    # Ask the OS which local interface the default route leaves through.
    $route = Find-NetRoute -RemoteIPAddress "8.8.8.8" -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($route -and $route.IPAddress) { return $route.IPAddress }
    $addr = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -First 1
    if ($addr) { return $addr.IPAddress }
    return $null
}

# PowerShell is case-insensitive, so this MUST NOT be called $network --
# that would overwrite the -Network parameter and trip its ValidateSet.
$networkLabel = "manual"
if (-not $NodeIp) {
    switch ($Network) {
        "Tailscale" {
            $NodeIp = Get-TailscaleIP
            $networkLabel = "Tailscale"
        }
        "Lan" {
            $NodeIp = Get-LanIP
            $networkLabel = "LAN"
        }
        default {
            $NodeIp = Get-TailscaleIP
            if ($NodeIp) {
                $networkLabel = "Tailscale"
            } else {
                $NodeIp = Get-LanIP
                $networkLabel = "LAN"
            }
        }
    }
}

if (-not $NodeIp) {
    throw "Could not detect an address. Re-run with -NodeIp <address>."
}

$config = Join-Path $livekitDir "livekit.generated.yaml"

# Read as UTF-8 and write as UTF-8 WITHOUT a BOM. A BOM makes the Go YAML
# parser fail with "control characters are not allowed".
$text = [System.IO.File]::ReadAllText($template, [System.Text.Encoding]::UTF8)
$text = [regex]::Replace($text, '(?m)^(\s*node_ip:\s*).*$', "`${1}$NodeIp")
[System.IO.File]::WriteAllText($config, $text, (New-Object System.Text.UTF8Encoding($false)))

Write-Host ""
Write-Host "LiveKit server" -ForegroundColor Cyan
Write-Host "  network : $networkLabel"
Write-Host "  node_ip : $NodeIp"
Write-Host "  ws      : ws://${NodeIp}:7880"
Write-Host "  config  : $config"
Write-Host ""
if ($networkLabel -eq "Tailscale") {
    Write-Host "Both machines must be signed in to the same tailnet." -ForegroundColor Yellow
    Write-Host "No firewall changes are needed on this path." -ForegroundColor Yellow
    Write-Host "The backend detects this address automatically." -ForegroundColor Yellow
} elseif ($networkLabel -eq "LAN") {
    Write-Host "LAN path checklist:" -ForegroundColor Yellow
    Write-Host "  1. Firewall, as Administrator:"
    Write-Host "       .\scripts\open-firewall.ps1 -Profile Public"
    Write-Host "     Campus and cafe Wi-Fi is usually Public. Check: Get-NetConnectionProfile"
    Write-Host "  2. Both machines on the same network, and no AP/client isolation."
    Write-Host "     Test from the other machine:  ping $NodeIp"
    Write-Host "  3. Put this in backend/.env -- the backend CANNOT auto-detect a LAN"
    Write-Host "     address while Tailscale is up, so this line is required:"
    Write-Host "       LIVEKIT_URL=ws://${NodeIp}:7880"
} else {
    Write-Host "Set LIVEKIT_URL=ws://${NodeIp}:7880 in backend/.env" -ForegroundColor Yellow
}
Write-Host ""

& $exe --config $config
