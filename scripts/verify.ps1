# Local quality gate mirroring CI: lint + typecheck + tests + coverage
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$env:PYTHONUTF8 = "1"

Write-Host "=== ruff ==="
ruff check engine/radiobiology tests/synthetic rbgyanx

Write-Host "=== black ==="
black --check engine/radiobiology tests/synthetic

Write-Host "=== mypy ==="
mypy engine/radiobiology --config-file pyproject.toml

Write-Host "=== pytest + coverage ==="
python -m pytest --import-mode=importlib --cov --cov-report=term-missing --cov-fail-under=70 -q

Write-Host "=== synthetic package ==="
python -m pytest tests/synthetic -v --import-mode=importlib

Write-Host "ALL VERIFY STEPS COMPLETE"
