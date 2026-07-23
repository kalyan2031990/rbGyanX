# Pre-delete verification for project_rbGyanx (run before removing legacy Desktop folders)
$ErrorActionPreference = "Stop"
$Root = "C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx"
Set-Location $Root

Write-Host "=== project_rbGyanx verification ===" -ForegroundColor Cyan

$checks = @(
    @{ Name = "engine"; Path = "engine\rbgyanx_engine\__init__.py" },
    @{ Name = "GUI"; Path = "rbgyanx_gui.py" },
    @{ Name = "DICOM cohort (local, optional)"; Path = "test_data\dicom_input" },
    @{ Name = "installer (build locally)"; Path = "dist\rbGyanX-1.0.0-full-Setup.exe" },
    @{ Name = "reports dir"; Path = "reports" },
    @{ Name = "plots dir"; Path = "plots" },
    @{ Name = "qa/reports"; Path = "qa\reports" }
)
foreach ($c in $checks) {
    $ok = Test-Path (Join-Path $Root $c.Path)
    $color = if ($ok) { "Green" } else { "Yellow" }
    Write-Host ("  [{0}] {1}" -f $(if ($ok) { "OK" } else { "MISSING" }), $c.Name) -ForegroundColor $color
}

Write-Host ""
Write-Host "Self-test (Python)..."
python -c @"
from pathlib import Path
from qa.self_test_engine import run_self_test
r = run_self_test(Path('.'))
s = r['summary']
print(f\"Status: {r['status']}  passed={s['passed']} warned={s['warned']} failed={s['failed']}\")
for t in r['results']:
    if t['status'] != 'PASS':
        print(f\"  {t['status']}: {t['name']} - {t['message']}\")
"@

Write-Host ""
Write-Host "Engine smoke (fast, no uncertainty)..."
$env:RBGYANX_ENGINE_PATH = Join-Path $Root "engine"
python -m rbgyanx_engine --dicom-dir (Join-Path $Root "test_data\dicom_input") --endpoint both --mode basic --cohort --output-dir (Join-Path $Root "_verify_out") --no-uncertainty 2>&1 | Select-Object -Last 3

Write-Host ""
Write-Host "Done. Safe to delete legacy folders if self-test failed=0 and engine exit 0." -ForegroundColor Cyan
