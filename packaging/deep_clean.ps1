# Remove caches and dev artifacts from project_rbGyanx (safe to re-run).
$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

$removeDirs = @(
    "__pycache__", ".pytest_cache", "engine_bundle", "build",
    "_smoke_physical", "_fix_smoke", "_r2_smoke", "rbgyanx_smoke_dicom"
)
foreach ($name in $removeDirs) {
    Get-ChildItem -Path $Root -Filter $name -Recurse -Directory -ErrorAction SilentlyContinue |
        ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }
}

Get-ChildItem -Path $Root -Include "*.pyc","*.pyo" -Recurse -File -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

Get-ChildItem -Path $Root -Filter "*.egg-info" -Recurse -Directory -ErrorAction SilentlyContinue |
    ForEach-Object { Remove-Item $_.FullName -Recurse -Force -ErrorAction SilentlyContinue }

Write-Host "Deep clean complete: $Root"
