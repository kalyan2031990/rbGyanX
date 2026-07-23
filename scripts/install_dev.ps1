# Editable dev install for the rbGyanX monorepo (no RBGYANX_ENGINE_PATH required).
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Installing rbgyanx-engine, advanced packages, and dev tools..."
python -m pip install --upgrade pip
python -m pip install -e "./engine[ml]" -e "./engine_advanced[pinn,dose3d]" -e "./engine_advanced_f[bayesian,pinn]" -e ".[dev,ml,torch,bayesian]"
Write-Host "Done. Run: pytest"
