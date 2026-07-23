# rbGyanX test runner — clears pyc before running to avoid stale cache issues
param(
    [switch]$Slow,
    [switch]$WithML
)

$ErrorActionPreference = "Stop"
$env:RBGYANX_ENGINE_PATH = "$PSScriptRoot\..\engine"
$env:PYTHONUTF8 = "1"
Set-Location "$PSScriptRoot\.."

# Clear bytecache
Get-ChildItem -Recurse -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter "__pycache__" -Directory -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

$args_list = @("--import-mode=importlib", "-v", "--tb=short")
if (-not $Slow) { $args_list += @("-m", "not slow") }

python -m pytest @args_list `
    engine/tests/ tests/ engine_advanced/tests/ engine_advanced_f/tests/
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m pytest tests/test_publication_suite.py --import-mode=importlib -v --tb=short
exit $LASTEXITCODE
