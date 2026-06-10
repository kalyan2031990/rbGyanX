# Test run summary

**Date (UTC):** 2026-06-10  
**Environment:** Windows, Python 3.14.2, repo root (no `RBGYANX_ENGINE_PATH`)

## Command

```powershell
.\scripts\install_dev.ps1
$env:PYTHONUTF8 = "1"
python -m pytest --import-mode=importlib -q --tb=no
```

## Result

| Metric | Value |
|--------|-------|
| Passed | 462 |
| Skipped | 3 |
| Failed | 0 |
| Exit code | 0 |

Skips: GUI headless (×2), optional `validation_utils` import.

## Fix applied

`engine/tests/test_radiobiology.py::test_calculator_mean_range` now aggregates all `TCP_*` model outputs (including registry extensions), matching `TCPCalculator` mean/range logic.

## Full validation (real + synthetic data)

```powershell
python scripts/run_validation_report.py
```

See `docs/validation_report.json` and `docs/TECHNICAL_DEVELOPMENT_NOTE.md`.

## Zenodo bundles

```powershell
.\scripts\build_zenodo_bundle.ps1
```

See `reproducibility/ZENODO_UPLOAD_GUIDE.md`.
