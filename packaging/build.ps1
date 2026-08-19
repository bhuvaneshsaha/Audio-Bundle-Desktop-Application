# Build standalone Admin and Client executables on Windows.
# Usage (from the repo root, with the venv activated):
#   .\packaging\build.ps1
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $Root

$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    $PythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
}
if (-not $PythonCmd) {
    throw "Python was not found. Activate the virtual environment first (.\venv\Scripts\Activate.ps1)."
}

& $PythonCmd.Source -m pip install -e ".[packaging]"
if ($LASTEXITCODE -ne 0) { throw "pip install failed." }
& $PythonCmd.Source -m PyInstaller --noconfirm --clean (Join-Path $Root "packaging\admin.spec")
if ($LASTEXITCODE -ne 0) { throw "Admin PyInstaller build failed." }
& $PythonCmd.Source -m PyInstaller --noconfirm --clean (Join-Path $Root "packaging\client.spec")
if ($LASTEXITCODE -ne 0) { throw "Client PyInstaller build failed." }

Write-Host "Built dist\AudioBundleAdmin.exe and dist\AudioBundleClient.exe"
