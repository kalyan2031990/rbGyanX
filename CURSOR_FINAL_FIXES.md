# rbGyanX — Cursor Final Fixes Prompt
# Fix all remaining issues including pre-existing dependency and config problems.
# Run each section, confirm pytest green, then move on.

---

## FIX-1 — pytest conftest ImportPathMismatchError

**Problem:** Running `pytest engine/tests/ tests/` together fails with
`ImportPathMismatchError: ('tests.conftest', ...)` because both `engine/tests/conftest.py`
and `tests/conftest.py` have the same module name but different physical paths.

**File:** `pytest.ini` (project root)

Replace the entire file:
```ini
[pytest]
testpaths = engine/tests tests engine_advanced/tests engine_advanced_f/tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*

# Prevent namespace collision between engine/tests and tests
# by giving each their own rootdir prefix
addopts = --import-mode=importlib -q

# Marker definitions
markers =
    slow: marks tests as slow (skipped in CI unless --runslow)
    requires_dicom: marks tests that need real DICOM data
    requires_xgboost: marks tests that need xgboost
    requires_lifelines: marks tests that need lifelines
    requires_torch: marks tests that need PyTorch
    requires_pymc: marks tests that need PyMC
```

**File:** `engine/tests/conftest.py`

Add `importlib` mode guard at the top — remove any `sys.path` manipulation that
duplicates what `pytest.ini` now handles:
```python
# engine/tests/conftest.py — engine-specific fixtures only
# sys.path for the engine root is handled by pytest.ini importlib mode
```

---

## FIX-2 — Optional dependencies: graceful skip for xgboost, lightgbm, lifelines

### 2a. `engine/ml_models/xgboost_tcp.py`
```python
# Replace the hard ImportError with a soft one:
try:
    import xgboost as xgb
    _XGB_AVAILABLE = True
except ImportError:
    _XGB_AVAILABLE = False

def _require_xgb():
    if not _XGB_AVAILABLE:
        raise ImportError(
            "xgboost>=1.7 required for XGBoost TCP model. "
            "Install with: pip install xgboost"
        )
```
In `XGBoostTCPModel.fit` and `predict`, call `_require_xgb()` at the start.

### 2b. `engine/ml_models/lgbm_tcp.py`
Same pattern with `lightgbm`:
```python
try:
    import lightgbm as lgb
    _LGBM_AVAILABLE = True
except ImportError:
    _LGBM_AVAILABLE = False
```

### 2c. `engine/statistical_models/cox_regression.py`
```python
try:
    from lifelines import CoxPHFitter
    _LIFELINES_AVAILABLE = True
except ImportError:
    _LIFELINES_AVAILABLE = False

def fit_cox_tcp(df, feature_cols, duration_col="followup_months", event_col="tcp_outcome"):
    if not _LIFELINES_AVAILABLE:
        raise ImportError(
            "lifelines>=0.27 required for Cox regression. "
            "Install with: pip install lifelines"
        )
    ...
```

### 2d. `engine/tests/test_ml_models.py`
Add skip markers to every test that needs xgboost/lgbm:
```python
import pytest
xgb_skip = pytest.mark.skipif(
    not _xgb_available(), reason="xgboost not installed"
)
lgbm_skip = pytest.mark.skipif(
    not _lgbm_available(), reason="lightgbm not installed"
)
```
Apply `@xgb_skip` / `@lgbm_skip` to relevant test functions.

### 2e. `engine/tests/test_statistical_models.py`
```python
import pytest
lifelines_skip = pytest.mark.skipif(
    not _lifelines_available(), reason="lifelines not installed"
)
# Apply to all Cox regression tests:
@lifelines_skip
def test_cox_harrell_c_above_chance(): ...
```

---

## FIX-3 — Bootstrap CI NaN in ntcp_calibration

**File:** `engine/validation/ntcp_calibration.py`

**Problem:** When synthetic data has very low event diversity, bootstrap resamples may
not include both event classes, causing MLE to fail on every resample → all CI NaN.

**Fix:** Add diversity check before attempting CI:
```python
def _bootstrap_ci_lkb(
    dvh_list, outcomes, td50_fit, m_fit, init_n, fix_n, n_bootstrap, bounds_td50, bounds_m
):
    """Bootstrap 95% CI. Returns (NaN, NaN) with warning if data too sparse."""
    y = np.asarray(outcomes, dtype=float)
    n_events = int(y.sum())
    n_nonevents = int((1 - y).sum())

    if n_events < 5 or n_nonevents < 5:
        logger.warning(
            "Bootstrap CI skipped: too few events (%d) or non-events (%d). "
            "Need ≥5 of each for reliable CI. Collect more outcome data.",
            n_events, n_nonevents,
        )
        return (math.nan, math.nan), (math.nan, math.nan)

    td50_boot, m_boot = [], []
    rng = np.random.default_rng(42)
    n = len(y)
    successes = 0

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        y_b = y[idx]
        # Skip resamples with no event diversity
        if y_b.sum() < 2 or (1 - y_b).sum() < 2:
            continue
        dvh_b = [dvh_list[i] for i in idx]
        if fix_n:
            def nll_b(p):
                return _nll_lkb_fixed_n(p, dvh_b, y_b, init_n)
            r = minimize(nll_b, x0=[td50_fit, m_fit], method="L-BFGS-B",
                         bounds=[bounds_td50, bounds_m])
        else:
            def nll_b(p):
                return _nll_lkb_free(p, dvh_b, y_b)
            r = minimize(nll_b, x0=[td50_fit, m_fit, init_n], method="L-BFGS-B",
                         bounds=[bounds_td50, bounds_m, (0.01, 1.5)])
        if r.success:
            td50_boot.append(r.x[0])
            m_boot.append(r.x[1])
            successes += 1

    if successes < 20:
        logger.warning(
            "Only %d/%d bootstrap resamples converged for CI. "
            "CI may be unreliable.", successes, n_bootstrap
        )

    def _ci(arr):
        if len(arr) < 10:
            return (math.nan, math.nan)
        return (float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5)))

    return _ci(td50_boot), _ci(m_boot)
```

Also rename the internal NLL functions consistently:
```python
# Private helpers — named for testability
def _nll_lkb_fixed_n(params, dvh_list, outcomes, n_fixed):
    """Negative log-likelihood for LKB probit with fixed n."""
    td50, m = params
    return _neg_log_likelihood_lkb((td50, m, n_fixed), dvh_list, outcomes)

def _nll_lkb_free(params, dvh_list, outcomes):
    """Negative log-likelihood for LKB probit with free n."""
    return _neg_log_likelihood_lkb(tuple(params), dvh_list, outcomes)

def _neg_log_likelihood_lkb(params, dvh_list, outcomes):
    """Core NLL — exposed for testability (CURSOR_FIXES §25)."""
    td50, m, n = params
    if td50 <= 0 or m <= 0 or n <= 0 or n > 1.5:
        return 1e10
    nll = 0.0
    for dvh, y in zip(dvh_list, outcomes):
        geud = _compute_geud(dvh["doses"], dvh["vols"], n)
        if math.isnan(geud):
            continue
        p = _lkb_probit_ntcp(geud, td50, m)
        p = max(1e-9, min(1 - 1e-9, p))
        nll -= y * math.log(p) + (1 - y) * math.log(1 - p)
    return nll
```

---

## FIX-4 — test_data/dicom_input placeholder

**File:** Create `test_data/dicom_input/.gitkeep`
**File:** Create `test_data/README.md`:
```markdown
# Test data

`dicom_input/` holds anonymised DICOM RT cohort for integration testing.

This directory is excluded from version control (PHI risk, binary size).

To run DICOM integration tests:
1. Place anonymised patient folders here (each with RTPLAN, RTDOSE, RTSTRUCT .dcm).
2. Run: `python -m rbgyanx_engine --dicom-dir test_data/dicom_input --endpoint both
         --cohort --output-dir out_dicom_test --no-uncertainty`

A 4-patient de-identified cohort is available to collaborators under a DTA.
Contact the corresponding author (see CITATION.cff).

For CI without real DICOM data, all engine tests use synthetic DVH fixtures
and do not require this directory.
```

In all tests that call `test_data/dicom_input`, wrap with:
```python
import pytest, os
dicom_available = os.path.isdir("test_data/dicom_input") and \
    any(f.endswith(".dcm") for root,_,files in
        os.walk("test_data/dicom_input") for f in files)
requires_dicom = pytest.mark.skipif(
    not dicom_available, reason="No DICOM test data in test_data/dicom_input"
)
```

---

## FIX-5 — dvh_shape_features stale .pyc (Windows dev environment)

**File:** `packaging/build_rbGyanX.ps1`

Add a clean-pyc step before build:
```powershell
# Clean stale bytecache before build
Write-Host "Cleaning stale .pyc files..."
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter "__pycache__" -Directory |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "Bytecache cleared."
```

**File:** `scripts/run_all_tests.ps1` (create if not exists):
```powershell
# rbGyanX test runner — clears pyc before running to avoid stale cache issues
param([switch]$Slow, [switch]$WithML)

$env:RBGYANX_ENGINE_PATH = "$PSScriptRoot\..\engine"
Set-Location "$PSScriptRoot\.."

# Clear bytecache
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

$args_list = @("--import-mode=importlib", "-v", "--tb=short")
if (-not $Slow) { $args_list += "-m not slow" }

python -m pytest @args_list `
    engine/tests/ tests/ engine_advanced/tests/ engine_advanced_f/tests/
```

---

## FIX-6 — Validation metrics: add Brier_95CI to dict output

**File:** `engine/validation/validation_metrics.py`

In `validation_result_to_dict`:
```python
def validation_result_to_dict(vr: ValidationResult) -> dict:
    return {
        "model":          vr.model_name,
        "n_patients":     vr.n_patients,
        "n_events":       vr.n_events,
        "AUC":            round(vr.auc, 3),
        "AUC_95CI":       f"[{vr.auc_ci_lower:.3f}, {vr.auc_ci_upper:.3f}]",
        "Brier":          round(vr.brier_score, 3),
        "Brier_95CI":     f"[{vr.brier_ci_lower:.3f}, {vr.brier_ci_upper:.3f}]",
        "Cal_slope":      round(vr.cal_slope, 3),
        "Cal_intercept":  round(vr.cal_intercept, 3),
        "HL_stat":        round(vr.hl_stat, 2),
        "HL_p":           round(vr.hl_p_value, 3),
        "ECE":            round(vr.ece, 3),
        "cal_adequate":   vr.hl_p_value > 0.05 if not math.isnan(vr.hl_p_value) else None,
    }
```

---

## Verification checklist after all fixes

```powershell
cd C:\Users\Sampa\OneDrive\Desktop\project_rbGyanx
$env:RBGYANX_ENGINE_PATH = "$PWD\engine"

# Clear pyc
Get-ChildItem -Recurse -Filter "*.pyc" | Remove-Item -Force -ErrorAction SilentlyContinue

# Full suite — should be 0 failures
python -m pytest engine/tests/ tests/ engine_advanced/tests/ engine_advanced_f/tests/ `
    --import-mode=importlib -q --tb=short 2>&1

# Publication suite specifically
python -m pytest tests/test_publication_suite.py -v --tb=short 2>&1

# Confirm optional deps skip cleanly
python -m pytest engine/tests/test_ml_models.py engine/tests/test_statistical_models.py `
    --import-mode=importlib -q 2>&1
```

Expected: all tests pass or skip. Zero failures.
