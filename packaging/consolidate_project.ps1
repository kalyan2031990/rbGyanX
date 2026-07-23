# Merge rbgyanx_dual + rbGyanX_cdss + py_tcpx test assets into Desktop\project_rbGyanx
# Usage: .\packaging\consolidate_project.ps1 [-Dest "C:\...\project_rbGyanx"]

param(
    [string]$Dest = "C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx",
    [string]$DualRoot = "",
    [string]$EngineRoot = "",
    [string]$PyTcpxRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $DualRoot) {
    $DualRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}
if (-not $EngineRoot) {
    $EngineRoot = (Join-Path (Split-Path $DualRoot -Parent) "rbGyanX_cdss")
    if (-not (Test-Path (Join-Path $EngineRoot "rbgyanx_engine\__init__.py"))) {
        $EngineRoot = "C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss"
    }
}
if (-not $PyTcpxRoot) {
    $PyTcpxRoot = "C:\Users\Sampa\OneDrive\Desktop\py_tcpx"
}

$EngineRoot = (Resolve-Path $EngineRoot).Path
$DualRoot = (Resolve-Path $DualRoot).Path

if (Test-Path $Dest) {
    Write-Host "Removing existing $Dest ..."
    Remove-Item -LiteralPath $Dest -Recurse -Force
}
New-Item -ItemType Directory -Path $Dest | Out-Null

$AppExclude = @(
    "dist", "build", "engine_bundle", "__pycache__", ".pytest_cache", ".cursor",
    "backups", "plots", "reports", ".git", "archived"
)

Write-Host "Copying desktop app from rbgyanx_dual ..."
robocopy $DualRoot $Dest /E /XD $AppExclude /XF *.pyc /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy app failed: $LASTEXITCODE" }

$EngineExclude = @(
    ".git", "__pycache__", ".pytest_cache", "dist", "build",
    "_smoke_physical", "_fix_smoke", "_r2_smoke", "rbgyanx_smoke_dicom",
    "rbgyanx_engine.egg-info", ".eggs"
)
$EngineDest = Join-Path $Dest "engine"
Write-Host "Copying engine into engine\ ..."
robocopy $EngineRoot $EngineDest /E /XD $EngineExclude /XF *.pyc /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
if ($LASTEXITCODE -ge 8) { throw "robocopy engine failed: $LASTEXITCODE" }

$TestSrc = Join-Path $PyTcpxRoot "py_tcpx_test_input"
if (Test-Path $TestSrc) {
    $TestDest = Join-Path $Dest "test_data\dicom_input"
    New-Item -ItemType Directory -Path (Split-Path $TestDest) -Force | Out-Null
    Write-Host "Copying DICOM test cohort to test_data\dicom_input ..."
    robocopy $TestSrc $TestDest /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
}

# Root metadata
if (Test-Path (Join-Path $EngineRoot "LICENSE")) {
    Copy-Item (Join-Path $EngineRoot "LICENSE") (Join-Path $Dest "LICENSE") -Force
}
if (Test-Path (Join-Path $DualRoot "VERSION.txt")) {
    Copy-Item (Join-Path $DualRoot "VERSION.txt") (Join-Path $Dest "VERSION.txt") -Force
}

Write-Host "Consolidated project: $Dest"
Write-Host "  engine\     = rbGyanX_cdss"
Write-Host "  test_data\  = py_tcpx DICOM cohort (if present)"

foreach ($d in @("reports", "plots", "qa\reports")) {
    $p = Join-Path $Dest $d
    if (-not (Test-Path $p)) { New-Item -ItemType Directory -Path $p -Force | Out-Null }
    $keep = Join-Path $p ".gitkeep"
    if (-not (Test-Path $keep)) { New-Item -ItemType File -Path $keep -Force | Out-Null }
}
