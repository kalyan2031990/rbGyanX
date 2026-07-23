# Build rbGyanX Windows setup (.exe installer) with Inno Setup 6
# Prerequisite: dist\rbGyanX from build_rbGyanX.ps1
# Usage:
#   .\packaging\build_installer.ps1
#   .\packaging\build_installer.ps1 -BuildApp   # PyInstaller + installer

param(
    [switch]$BuildApp,
    [string]$EngineRoot = ""
)

$ErrorActionPreference = "Stop"
$PackagingDir = $PSScriptRoot
$DualRoot = (Resolve-Path (Join-Path $PackagingDir "..")).Path
$AppDir = Join-Path $DualRoot "dist\rbGyanX"
$AppVersion = "1.0.0"

if ($BuildApp) {
    & (Join-Path $PackagingDir "build_rbGyanX.ps1") @PSBoundParameters
}

if (-not (Test-Path (Join-Path $AppDir "rbGyanX.exe"))) {
    throw "Missing $AppDir\rbGyanX.exe. Run .\packaging\build_rbGyanX.ps1 first."
}

# User guide beside executable (Start Menu link)
$GuideSrc = Join-Path $DualRoot "docs\RBGYANX_1.0_DESKTOP.md"
if (Test-Path $GuideSrc) {
    Copy-Item $GuideSrc (Join-Path $AppDir "RBGYANX_1.0_DESKTOP.md") -Force
}

$IsccCandidates = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "${env:LocalAppData}\Programs\Inno Setup 6\ISCC.exe"
)
$Iscc = $IsccCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $Iscc) {
    Write-Host ""
    Write-Host "Inno Setup 6 not found. Install from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "Then re-run: .\packaging\build_installer.ps1"
    Write-Host ""
    Write-Host "Portable app is still ready at: $AppDir"
    exit 2
}

$Iss = Join-Path $PackagingDir "rbGyanX.iss"
$AppSourceAbs = (Resolve-Path $AppDir).Path

Write-Host "Compiling installer with Inno Setup ..."
& $Iscc $Iss "/DMyAppSource=$AppSourceAbs" "/DMyAppVersion=$AppVersion"

$SetupExe = Join-Path $DualRoot "dist\rbGyanX-$AppVersion-full-Setup.exe"
if (-not (Test-Path $SetupExe)) {
    $alt = Get-ChildItem (Join-Path $DualRoot "dist") -Filter "rbGyanX-*-full-Setup.exe" -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($alt) {
        if ($alt.FullName -ne $SetupExe) {
            Move-Item -LiteralPath $alt.FullName -Destination $SetupExe -Force
        }
    }
}
if (-not (Test-Path $SetupExe)) {
    throw "Installer build failed. Expected: $SetupExe"
}

Write-Host ""
Write-Host "Installer ready:" -ForegroundColor Green
Write-Host "  $SetupExe"
Write-Host ""
Write-Host "Distribute this file to clinicians (includes uninstaller via Windows Settings)."
