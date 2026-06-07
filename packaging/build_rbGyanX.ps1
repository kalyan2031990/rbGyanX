# Build rbGyanX 1.0 standalone desktop (Windows)
# Usage:
#   .\packaging\build_rbGyanX.ps1 -BuildInstaller
#   .\packaging\build_rbGyanX.ps1 -BuildInstaller -IncludeTensorFlow:$false   # lean (no TF)

param(
    [string]$EngineRoot = "",
    [switch]$SkipEngineSync,
    [switch]$BuildInstaller,
    [switch]$IncludeTensorFlow = $true
)

$ErrorActionPreference = "Stop"
$DualRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Get-TfCapablePythonExe {
    foreach ($tag in @("-3.10", "-3.11", "-3.12")) {
        try {
            $exe = & py $tag -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) {
                return $exe.Trim()
            }
        } catch {
            continue
        }
    }
    return $null
}

function Test-PythonSupportsTensorFlow {
    param([string]$PythonExe)
    & $PythonExe -c "import sys; v=sys.version_info; raise SystemExit(0 if v < (3,13) else 1)" 2>$null
    return $LASTEXITCODE -eq 0
}

if (-not $EngineRoot) {
    $candidates = @(
        (Join-Path $DualRoot "engine"),
        (Join-Path (Split-Path $DualRoot -Parent) "rbGyanX_cdss"),
        "C:\Users\Sampa\OneDrive\Desktop\rbGyanX_cdss",
        "C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx\engine"
    )
    foreach ($c in $candidates) {
        if (Test-Path (Join-Path $c "rbgyanx_engine\__init__.py")) {
            $EngineRoot = (Resolve-Path $c).Path
            break
        }
    }
}
if (-not $EngineRoot -or -not (Test-Path (Join-Path $EngineRoot "rbgyanx_engine\__init__.py"))) {
    throw "rbGyanX_cdss not found. Pass -EngineRoot path to the engine repository."
}

$Bundle = Join-Path $DualRoot "engine_bundle"
if (-not $SkipEngineSync) {
    Write-Host "Syncing engine into engine_bundle ..."
    if (Test-Path $Bundle) { Remove-Item -Recurse -Force $Bundle }
    New-Item -ItemType Directory -Path $Bundle | Out-Null
    $excludeDirs = @(".git", "tests", "__pycache__", ".pytest_cache", "dist", "build",
        "rbgyanx_smoke_dicom", "_fix_smoke", "_r2_smoke", "engine_bundle")
    $engineExclude = $excludeDirs + @("rbgyanx_engine.egg-info", ".eggs")
    robocopy $EngineRoot $Bundle /E /XD $engineExclude /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
    if ($LASTEXITCODE -ge 8) { throw "robocopy engine sync failed with code $LASTEXITCODE" }
}

Set-Location $DualRoot

# Clean stale bytecache before build
Write-Host "Cleaning stale .pyc files..."
Get-ChildItem -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Bytecache cleared."

$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = "python"
}

if ($IncludeTensorFlow) {
    $tfPy = Get-TfCapablePythonExe
    if (-not $tfPy) {
        throw @"
-IncludeTensorFlow requires Python 3.10, 3.11, or 3.12 (TensorFlow has no wheel for 3.13+).
Install Python 3.10 from python.org or run: winget install Python.Python.3.10
Or build lean: .\packaging\build_rbGyanX.ps1 -BuildInstaller -IncludeTensorFlow:`$false
"@
    }
    if (-not (Test-PythonSupportsTensorFlow $PythonExe)) {
        Write-Host "Switching build interpreter to TensorFlow-capable Python: $tfPy"
        $PythonExe = $tfPy
    }
    $env:RBGYANX_INCLUDE_TENSORFLOW = "1"
} else {
    $env:RBGYANX_INCLUDE_TENSORFLOW = "0"
    $pyMinor = & $PythonExe -c "import sys; print(sys.version_info.minor)"
    $pyMajor = & $PythonExe -c "import sys; print(sys.version_info.major)"
    if ($pyMajor -gt 3 -or ($pyMajor -eq 3 -and [int]$pyMinor -ge 13)) {
        Write-Warning @"
Python $($pyMajor).$($pyMinor): lean build OK. For TensorFlow in the installer use -IncludeTensorFlow (needs 3.10-3.12).
"@
    }
}

$BuildReq = Join-Path $PSScriptRoot "requirements-build.txt"
if (-not (Test-Path $BuildReq)) {
    throw "Missing packaging\requirements-build.txt"
}

if ($IncludeTensorFlow) {
    $TfReq = Join-Path $PSScriptRoot "requirements-build-tensorflow.txt"
    Write-Host "Installing dependencies (full build with TensorFlow) using: $PythonExe"
    & $PythonExe -m pip install -q --upgrade pip
    & $PythonExe -m pip install -q -r $TfReq
    & $PythonExe (Join-Path $PSScriptRoot "verify_tensorflow.py")
} else {
    Write-Host "Installing dependencies (lean build, no TensorFlow) using: $PythonExe"
    & $PythonExe -m pip install -q --upgrade pip
    & $PythonExe -m pip install -q -r $BuildReq
}

& $PythonExe -m pip install -q pyinstaller
& $PythonExe -m pip install -q -e $EngineRoot

Write-Host "Running PyInstaller (INCLUDE_TENSORFLOW=$($env:RBGYANX_INCLUDE_TENSORFLOW)) ..."
& $PythonExe -m PyInstaller packaging\rbGyanX.spec --noconfirm --distpath dist --workpath build

$OutDir = Join-Path $DualRoot "dist\rbGyanX"
if (-not (Test-Path (Join-Path $OutDir "rbGyanX.exe"))) {
    throw "Build failed: rbGyanX.exe not found in dist\rbGyanX"
}

# Write build manifest for support / QA
$manifest = @{
    include_tensorflow = ($env:RBGYANX_INCLUDE_TENSORFLOW -eq "1")
    python             = (& $PythonExe -c "import sys; print(sys.version)" 2>$null)
}
if ($IncludeTensorFlow) {
    $manifest.tensorflow = (& $PythonExe -c "import tensorflow as tf; v=getattr(tf,'__version__',None) or getattr(getattr(tf,'version',None),'VERSION',''); print(v)" 2>$null)
}
$manifest | ConvertTo-Json | Set-Content (Join-Path $OutDir "build_manifest.json") -Encoding UTF8

Copy-Item (Join-Path $DualRoot "VERSION.txt") $OutDir -ErrorAction SilentlyContinue
$DestBundle = Join-Path $OutDir "engine_bundle"
if (Test-Path $Bundle) {
    if (Test-Path $DestBundle) { Remove-Item -Recurse -Force $DestBundle }
    Copy-Item -Recurse $Bundle $DestBundle
}

Write-Host ""
Write-Host "Build complete: $OutDir"
if ($IncludeTensorFlow) {
    Write-Host "TensorFlow: bundled (SHAP deep / future DL models). Installer will be larger (~400MB+)."
} else {
    Write-Host "TensorFlow: not included (lean installer)."
}
Write-Host "Run: $OutDir\rbGyanX.exe"

if ($BuildInstaller) {
    & (Join-Path $PSScriptRoot "build_installer.ps1")
}
