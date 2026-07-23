# Build Zenodo reproduction archives: synthetic (public) + real (restricted upload).
# Usage: .\scripts\build_zenodo_bundle.ps1 [-InputRoot "C:\...\input_folders"]
param(
    [string]$InputRoot = "C:\Users\Sampa\OneDrive\Desktop\input_folders",
    [string]$Version = "1.0.0"
)

$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
Set-Location $Root

$Dist = Join-Path $Root "reproducibility\dist"
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

Write-Host "==> Generating synthetic cohort and data inventory..."
python -c @"
from pathlib import Path
import shutil
from synthetic_data_generator import SyntheticClinicalDataGenerator
out = Path('test_data/synthetic_cohort')
if out.exists():
    shutil.rmtree(out)
out.mkdir(parents=True)
gen = SyntheticClinicalDataGenerator(n_patients=30, random_seed=42)
gen.generate_complete_dataset(str(out))
print('Synthetic cohort:', out.resolve())
"@
python scripts/inventory_test_data.py --input-root $InputRoot

Write-Host "==> Running pytest (results -> reproducibility/dist/pytest_results.txt)..."
$env:PYTHONUTF8 = "1"
python -m pytest --import-mode=importlib -q --tb=no 2>&1 | Tee-Object (Join-Path $Dist "pytest_results.txt")

Write-Host "==> Building synthetic Zenodo bundle..."
$SynthStaging = Join-Path $env:TEMP "rbgyanx_zenodo_synth_$Version"
if (Test-Path $SynthStaging) { Remove-Item $SynthStaging -Recurse -Force }
New-Item -ItemType Directory -Force -Path $SynthStaging | Out-Null

$SynthItems = @(
    @{ Src = "test_data\synthetic_cohort"; Dst = "synthetic_cohort" },
    @{ Src = "tests\synthetic"; Dst = "tests_synthetic" },
    @{ Src = "engine\tests\synthetic_data"; Dst = "engine_synthetic_data" },
    @{ Src = "reproducibility\DATA_INVENTORY.json"; Dst = "DATA_INVENTORY.json" },
    @{ Src = "docs\validation_report.json"; Dst = "validation_report.json" },
    @{ Src = "requirements-lock.txt"; Dst = "requirements-lock.txt" }
)
foreach ($item in $SynthItems) {
    $srcPath = Join-Path $Root $item.Src
    $dstPath = Join-Path $SynthStaging $item.Dst
    if (Test-Path $srcPath) {
        Copy-Item $srcPath $dstPath -Recurse -Force
    }
}
Copy-Item (Join-Path $Dist "pytest_results.txt") (Join-Path $SynthStaging "pytest_results.txt") -Force
Copy-Item (Join-Path $Root "reproducibility\README_SYNTHETIC.md") (Join-Path $SynthStaging "README.md") -Force

$SynthZip = Join-Path $Dist "rbGyanX_synthetic_test_data_v$Version.zip"
if (Test-Path $SynthZip) { Remove-Item $SynthZip -Force }
Compress-Archive -Path (Join-Path $SynthStaging "*") -DestinationPath $SynthZip -Force
Remove-Item $SynthStaging -Recurse -Force

Write-Host "==> Building real-data Zenodo bundle (excludes validation run outputs)..."
$RealSrc = Join-Path $InputRoot "rbgyanx_test_data"
$RealStaging = Join-Path $env:TEMP "rbgyanx_zenodo_real_$Version"
if (Test-Path $RealStaging) { Remove-Item $RealStaging -Recurse -Force }
$RealDst = Join-Path $RealStaging "rbgyanx_test_data"
New-Item -ItemType Directory -Force -Path $RealDst | Out-Null

if (Test-Path $RealSrc) {
    $exclude = @('_validation_*', '_integration_*', '_test_*')
    Get-ChildItem $RealSrc -Directory | Where-Object {
        $n = $_.Name
        -not ($n -like '_validation_*' -or $n -like '_integration_*' -or $n -like '_test_*')
    } | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $RealDst $_.Name) -Recurse -Force
    }
    Get-ChildItem $RealSrc -File | ForEach-Object {
        Copy-Item $_.FullName (Join-Path $RealDst $_.Name) -Force
    }
}
Copy-Item (Join-Path $Root "reproducibility\DATA_INVENTORY.json") (Join-Path $RealStaging "DATA_INVENTORY.json") -Force
Copy-Item (Join-Path $Root "reproducibility\README_REAL_DATA.md") (Join-Path $RealStaging "README.md") -Force

$RealZip = Join-Path $Dist "rbGyanX_real_test_data_v$Version.zip"
if (Test-Path $RealZip) { Remove-Item $RealZip -Force }
Compress-Archive -Path (Join-Path $RealStaging "*") -DestinationPath $RealZip -Force
Remove-Item $RealStaging -Recurse -Force

Write-Host ""
Write-Host "Done. Upload to Zenodo:"
Write-Host "  Public:     $SynthZip"
Write-Host "  Restricted: $RealZip  (enable 'restricted access' on Zenodo)"
Write-Host "See reproducibility/ZENODO_UPLOAD_GUIDE.md"
