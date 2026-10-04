# Installs the in-app fallback script into DaVinci Resolve's Scripts > Utility menu.
#   powershell -ExecutionPolicy Bypass -File .\install_inapp.ps1
$ErrorActionPreference = "Stop"
$dest = Join-Path $env:APPDATA "Blackmagic Design\DaVinci Resolve\Support\Fusion\Scripts\Utility"
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Force (Join-Path $PSScriptRoot "inapp\DVR_VO_Sync_apply_last_plan.py") $dest
Write-Host "Installed to $dest" -ForegroundColor Green
Write-Host "Restart Resolve, then: Workspace > Scripts > Utility > DVR_VO_Sync_apply_last_plan"
Write-Host "Resolve's in-app Python also needs Python 3.11+ installed system-wide (python.org)."
