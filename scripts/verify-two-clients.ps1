# Verify that two clients can join the same room and both publish media.
#
#   .\scripts\verify-two-clients.ps1
#   .\scripts\verify-two-clients.ps1 -Room demo-hci -WaitSeconds 30
#
# Opens two headless Chrome windows with a FAKE microphone and camera
# (--use-fake-device-for-media-stream), so it needs no real hardware and can run
# on one machine. It then asks the backend who is in the room.
#
# This proves the whole path: token -> signaling -> WebRTC -> media publish.
# It does NOT prove real speakers and microphones work, which still needs the
# two-machine manual test in the README.
#
# Requires: LiveKit, backend and frontend already running.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads .ps1 files
# without a BOM as ANSI, which turns Vietnamese diacritics into mojibake.

param(
    [string]$Room        = "demo-hci",
    [string]$FrontendUrl = "http://localhost:5173",
    [string]$BackendUrl  = "http://localhost:8000",
    [int]$WaitSeconds    = 20,
    # Extra Chrome flags, e.g. to reproduce what a browser would do without
    # the secure-context exemption:
    #   -ExtraChromeArgs "--unsafely-treat-insecure-origin-as-secure=http://100.82.57.5:5173"
    [string[]]$ExtraChromeArgs = @()
)

$ErrorActionPreference = "Stop"

$candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
)
$chrome = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $chrome) {
    throw "No Chrome or Edge found. Install one, or run the two-machine test manually (see README)."
}

$profiles = @()
$started  = @()

try {
    foreach ($n in 1, 2) {
        $profile = Join-Path $env:TEMP "ima-verify-client$n"
        Remove-Item $profile -Recurse -Force -ErrorAction SilentlyContinue
        $profiles += $profile

        $url = "$FrontendUrl/?room=$Room&name=May-$n"
        Write-Host "Client $n -> $url"

        $chromeArgs = @(
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            "--autoplay-policy=no-user-gesture-required",
            "--user-data-dir=$profile"
        )
        $chromeArgs += $ExtraChromeArgs
        $chromeArgs += $url
        $started += Start-Process -FilePath $chrome -ArgumentList $chromeArgs -PassThru
    }

    Write-Host ""
    Write-Host "Waiting ${WaitSeconds}s for both clients to connect and publish..." -ForegroundColor Cyan
    Start-Sleep -Seconds $WaitSeconds

    # Invoke-RestMethod hands a JSON array back as ONE object, so pipe it through
    # ForEach-Object to flatten it. Without this, .Count is always 1.
    $participants = @(
        Invoke-RestMethod -Uri "$BackendUrl/api/rooms/$Room/participants" -TimeoutSec 15 |
            ForEach-Object { $_ }
    )
}
finally {
    foreach ($proc in $started) {
        # /T kills the whole process tree; headless Chrome spawns children.
        # Go through cmd: PowerShell 5.1 turns a native command's stderr into a
        # terminating error under $ErrorActionPreference = "Stop", which would
        # abort this script right here before it can report the result.
        & cmd /c "taskkill /PID $($proc.Id) /T /F > nul 2>&1" | Out-Null
    }
    Start-Sleep -Milliseconds 500
    foreach ($profile in $profiles) {
        Remove-Item $profile -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Participants in '$Room': $($participants.Count)"
foreach ($p in $participants) {
    Write-Host ("  {0,-20} audio={1} video={2}" -f $p.name, $p.audio_tracks, $p.video_tracks)
}
Write-Host ""

# Both clients must have published BOTH an audio and a video track. Being in the
# room is not enough: a client can join and publish nothing.
$ready = @($participants | Where-Object { $_.audio_tracks -ge 1 -and $_.video_tracks -ge 1 })
if ($participants.Count -ge 2 -and $ready.Count -ge 2) {
    Write-Host "PASS - two clients joined, both published audio and video." -ForegroundColor Green
    exit 0
}

Write-Host "FAIL - expected 2 participants each publishing audio and video." -ForegroundColor Red
Write-Host "Got $($participants.Count) participant(s), $($ready.Count) with both tracks." -ForegroundColor Red
Write-Host "Check that all three services are running and that node_ip matches LIVEKIT_URL." -ForegroundColor Yellow
exit 1
