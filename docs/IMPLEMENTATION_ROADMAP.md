# rbGyanX — CURSOR_FIXES implementation roadmap

Source: [`CURSOR_FIXES.md`](../CURSOR_FIXES.md).

## Status (Parts A–F)

| Phase | Scope | Status |
|-------|--------|--------|
| **A** | §1–15 Bug fixes & safety | **Done** |
| **C** | §22–23 Prostate/pelvic/liver + validation metrics | **Done** |
| **D** | §24–26 ΔNTCP, MLE calibration, outcome schema | **Done** |
| **B** | §16–21 Advanced architecture (`engine_advanced/`) | **Done** |
| **E** | §27–28 3D dose + dosiomics | **Done** |
| **F** | §29–30 Bayesian + full PINN training (`engine_advanced_f/`) | **Done** |

## Part B — `engine_advanced/` (ADVANCED mode only)

- §16 `clinical_features_csv` on `RunConfig` + merge in `results_to_feature_df`
- §17 `dicom_io/dvh_shape_features.py` (lazy import from calculators)
- §18 `radiobiology/model_registry.py` + TCP/NTCP registry hooks
- §19 PINN stub: `rbgyanx_advanced/pinn/` + `register_pinn_models()`
- §20 `extract_3d_dose_array` stub in core; full path in `rbgyanx_advanced/dose3d/`
- §21 Manifesto section appended in `docs/RBGYANX_MANIFESTO.md`

Wiring: `engine.py` calls `enable_advanced_analysis()` when `mode == "advanced"` only. BASIC unchanged.

## Part E

- `rbgyanx_advanced/dose3d/dose_grid_extractor.py` (DICOM when deps present; synthetic voxels otherwise)
- `rbgyanx_advanced/dose3d/dosiomics.py` (IBSI-style first-order features)
- Dosiomics merged into cohort features in ADVANCED runs

## Full test suite

```powershell
cd C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx
$env:PYTHONUTF8 = "1"
.\scripts\run_all_tests.ps1
```

Or separately:

```powershell
python -m pytest engine/tests/ engine_advanced/tests/ engine_advanced_f/tests/ -q
python -m pytest tests/ -q
```

**Current:** engine + advanced + Part F + root tests pass on synthetic data (Bayesian emulation; PINN skipped if torch absent).

## Part F — `engine_advanced_f/` (ADVANCED mode only)

- §29 `rbgyanx_advanced_f/bayesian/ntcp_bayesian.py` — bootstrap emulation by default; PyMC optional (`pip install pymc arviz`)
- §30 `rbgyanx_advanced_f/pinn/train_pinn.py` — BCE + physics + boundary losses; checkpoint with `feat_means` / `feat_stds` / `feat_names`
- `RunConfig`: `enable_bayesian_ntcp`, `bayesian_ntcp_trace_dir`, `pinn_train`, `pinn_model_dir`, `pinn_epochs`
- Wiring: `engine.py` calls `enable_part_f_analysis()` when ADVANCED and Part F flags set

## Optional extras

- Install `torch` for PINN training: `pip install torch`
- Install `pymc arviz` for full MCMC Bayesian NTCP (emulation works without)
- Install `pydicom scikit-image` for real 3D dose extraction (optional)
