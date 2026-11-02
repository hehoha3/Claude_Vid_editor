param([switch]$YouTube)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command ffmpeg -ErrorAction SilentlyContinue) -or -not (Get-Command ffprobe -ErrorAction SilentlyContinue)) {
    throw 'Install FFmpeg first: winget install Gyan.FFmpeg; reopen PowerShell.'
}
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    py -3.11 -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.11 x64 or create .venv with Python 3.12.' }
}
$target = if ($YouTube) { '.[youtube]' } else { '.' }
& .venv\Scripts\python.exe -m pip install -e $target
if ($LASTEXITCODE -ne 0) { throw 'Dependency install failed.' }
& .venv\Scripts\python.exe -m unittest discover -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed; do not use the workspace yet.' }
Write-Host 'Ready. Open a clean Resolve project named exactly like the video folder; External scripting = Local.'
