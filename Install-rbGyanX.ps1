# rbGyanX 1.0 — developer install (GUI + engine, no frozen exe)
# Run from PowerShell: .\Install-rbGyanX.ps1

$ErrorActionPreference = "Stop"
$DualRoot = $PSScriptRoot
$EngineCandidates = @(
    (Join-Path $DualRoot "engine"),
    (Join-Path (Split-Path $DualRoot -Parent) "rbGyanX_cdss"),
    "C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss",
    "C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx\engine"
)
$EngineRoot = $null
foreach ($c in $EngineCandidates) {
    if (Test-Path (Join-Path $c "rbgyanx_engine\__init__.py")) {
        $EngineRoot = (Resolve-Path $c).Path
        break
    }
}
if (-not $EngineRoot) {
    throw "Could not find rbGyanX_cdss. Clone it next to rbgyanx_dual or set path in this script."
}

Set-Location $DualRoot
python -m pip install --upgrade pip
$BuildReq = Join-Path $DualRoot "packaging\requirements-build.txt"
if (Test-Path $BuildReq) {
    python -m pip install -r $BuildReq
} else {
    python -m pip install -r requirements.txt
}
python -m pip install -e $EngineRoot

$env:RBGYANX_ENGINE_PATH = $EngineRoot
Write-Host ""
Write-Host "Installed. Engine: $EngineRoot"
Write-Host "Launch GUI:  python rbgyanx_gui.py"
Write-Host "Build app:       .\packaging\build_rbGyanX.ps1"
Write-Host "Build installer: .\packaging\build_rbGyanX.ps1 -BuildInstaller"
