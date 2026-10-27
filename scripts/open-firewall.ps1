# Open the Windows Firewall ports the second machine needs.
# MUST be run from an Administrator PowerShell.
#
#   .\scripts\open-firewall.ps1                    # Private networks only
#   .\scripts\open-firewall.ps1 -Profile Public    # campus / cafe Wi-Fi
#   .\scripts\open-firewall.ps1 -Profile Any
#
# WHY THE PROFILE MATTERS: Windows classifies every network as Domain, Private
# or Public. A firewall rule only applies to the profile it was created for.
# Most home networks are Private, but most CAMPUS and CAFE Wi-Fi is PUBLIC.
# If you create a Private-only rule and then demo on a Public network, the rule
# silently does nothing and the second machine cannot connect.
#
# Check the current profile with:  Get-NetConnectionProfile
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, which turns Vietnamese diacritics into mojibake.

param(
    [ValidateSet("Private", "Public", "Domain", "Any")]
    [string]$Profile = "Private"
)

$ErrorActionPreference = "Stop"

$identity  = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Administrator rights required. Open PowerShell with 'Run as administrator' and try again."
}

Write-Host "Current networks:" -ForegroundColor Cyan
Get-NetConnectionProfile |
    Select-Object InterfaceAlias, Name, NetworkCategory |
    Format-Table -AutoSize | Out-String | Write-Host

Write-Host "Adding inbound rules for profile: $Profile" -ForegroundColor Cyan
Write-Host ""

$rules = @(
    @{ Name = "IMA LiveKit HTTP";  Port = "7880";      Proto = "TCP" },
    @{ Name = "IMA LiveKit RTC";   Port = "7881";      Proto = "TCP" },
    @{ Name = "IMA LiveKit Media"; Port = "7882-7892"; Proto = "UDP" },
    @{ Name = "IMA Backend API";   Port = "8000";      Proto = "TCP" },
    @{ Name = "IMA Frontend Dev";  Port = "5173";      Proto = "TCP" }
)

foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if ($existing) {
        # Rule exists but may have been created for a different profile.
        Set-NetFirewallRule -DisplayName $rule.Name -Profile $Profile -Enabled True
        Write-Host "Updated profile: $($rule.Name) -> $Profile" -ForegroundColor DarkGray
        continue
    }
    New-NetFirewallRule `
        -DisplayName $rule.Name `
        -Direction Inbound `
        -Action Allow `
        -Protocol $rule.Proto `
        -LocalPort $rule.Port `
        -Profile $Profile | Out-Null
    Write-Host "Added: $($rule.Name)  ($($rule.Proto) $($rule.Port))" -ForegroundColor Green
}

Write-Host ""
Write-Host "Done." -ForegroundColor Green
Write-Host ""
Write-Host "Next, point LiveKit at the Wi-Fi address of THIS machine:" -ForegroundColor Yellow
Write-Host "  Get-NetIPAddress -AddressFamily IPv4 | Where-Object InterfaceAlias -eq Wi-Fi"
Write-Host "  .\scripts\start-livekit.ps1 -NodeIp <wifi-ip>"
Write-Host ""
Write-Host "If the second machine still cannot connect, the Wi-Fi network probably" -ForegroundColor Yellow
Write-Host "blocks device-to-device traffic (AP / client isolation). Campus and cafe" -ForegroundColor Yellow
Write-Host "networks commonly do. That cannot be fixed from this machine." -ForegroundColor Yellow
Write-Host "Test it: on the second machine, run  ping <wifi-ip-of-this-machine>" -ForegroundColor Yellow
Write-Host "Ping fails while both machines are on the same Wi-Fi -> isolation." -ForegroundColor Yellow
Write-Host "Fall back to Tailscale, which is not affected." -ForegroundColor Yellow
