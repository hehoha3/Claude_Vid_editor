# dvr-cowork setup for Windows 10/11
# Usage (PowerShell, inside the workspace folder):
#   powershell -ExecutionPolicy Bypass -File .\setup.ps1
# Options:
#   -SkipModel     do not pre-download the Whisper model now
#   -Python "C:\Path\python.exe"   force a specific interpreter
param(
    [switch]$SkipModel,
    [string]$Python = ""
)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

function Test-Py([string]$exe, [string[]]$pre) {
    try {
        $v = & $exe @pre -c "import sys,struct;print('%d.%d %d' % (sys.version_info[0], sys.version_info[1], struct.calcsize('P')*8))" 2>$null
        if ($LASTEXITCODE -ne 0 -or -not $v) { return $null }
        $parts = $v.Trim().Split(" ")
        $ver = [version]$parts[0]
        if ($ver -ge [version]"3.11" -and $parts[1] -eq "64") { return $parts[0] }
    } catch { }
    return $null
}

$pyExe = $null; $pyPre = @()
if ($Python) {
    if (Test-Py $Python @()) { $pyExe = $Python }
} else {
    foreach ($v in @("3.11", "3.12", "3.13")) {
        if (Test-Py "py" @("-$v")) { $pyExe = "py"; $pyPre = @("-$v"); break }
    }
    if (-not $pyExe -and (Test-Py "python" @())) { $pyExe = "python" }
}
if (-not $pyExe) {
    Write-Host "No 64-bit Python 3.11+ found. Install Python 3.11 or 3.12 from python.org (tick 'Add to PATH'), then re-run." -ForegroundColor Red
    exit 1
}
Write-Host "Using Python: $pyExe $pyPre" -ForegroundColor Cyan

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    & $pyExe @pyPre -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

& $venvPy -m pip install --upgrade pip --quiet
& $venvPy -m pip install -e . --quiet
if ($LASTEXITCODE -ne 0) { throw "pip install failed" }
Write-Host "Python packages installed." -ForegroundColor Green

if (-not $SkipModel) {
    Write-Host "Downloading Whisper model (about 0.5 GB, one time)..." -ForegroundColor Cyan
    & $venvPy -m dvr_cowork prefetch
}

Write-Host ""
Write-Host "Self-test (no Resolve needed):" -ForegroundColor Cyan
& $venvPy -m tests.test_pipeline
Write-Host ""
Write-Host "Resolve check:" -ForegroundColor Cyan
& $venvPy -m dvr_cowork doctor
Write-Host ""
Write-Host "Done. Open Claude Code in this folder:  claude" -ForegroundColor Green
Write-Host "Then:  /sync-vo `"D:\path\narration.mp3`" `"D:\path\timestamps.txt`""
