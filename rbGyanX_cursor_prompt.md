# Cursor task — align rbGyanX with the Medical Physics manuscript and ship v1.0.0

You are working in the **rbGyanX** repository (https://github.com/kalyan2031990/rbGyanX).
Goal: make the codebase match, exactly, the claims of the accompanying methods/software
paper, add a reproducible paper-figure capsule, and cut a clean `v1.0.0` release. Do **not**
invent clinical results, do **not** add patient data, and do **not** weaken the safety
contract. Work on a branch `release/v1.0.0` and open a PR; push only after the full test
suite passes locally.

## 0. Orient first (do this before editing)
1. Read `README*`, `pyproject.toml`/`setup.*`, `VERSION*`, `CITATION.cff`, and the package
   layout. List the actual module paths for: the run controller (`run_analysis`), the NTCP
   primitives, the TCP models, UTCP, the calibration/validation layer, CCS, uNTCP, the
   four-tier harness, and the PINN/Bayesian code.
2. Run the existing test suite and record the exact pass/skip/fail counts and the total
   number of tests. **Report this number back** — the paper cites a "129-test publication
   suite"; confirm or correct it.
Treat the bullets below as intent: where a feature already exists, **align** it to the spec;
where it is missing, **create** it. Reconcile with the real code; flag any conflict instead
of silently overwriting.

## 1. Version single-source-of-truth (blocking)
- Decide one canonical version: **`1.0.0`**.
- Set it in ONE place (e.g. `rbgyanx_engine/__init__.py: __version__`) and have everything
  else read from it: `VERSION.txt`, `CITATION.cff` (`version:` and `date-released:`),
  `pyproject.toml`, installer metadata, and any `--version` CLI string.
- Add a test `tests/test_version_consistency.py` asserting all surfaced versions equal
  `__version__`. The known prior mismatch (`VERSION.txt` 1.0.0 vs `CITATION.cff` 2.0.0) must
  be eliminated.

## 2. NaN-safety contract (must match paper §2.B)
- Ensure all three NTCP primitives (LKB probit, Niemierko log-logistic, Relative Seriality)
  return `float('nan')` — **never `0.0`** — for degenerate input: missing/None gEUD,
  non-positive `TD50`/`m`/`gamma`, or a zero-volume / empty DVH.
- Add/confirm `tests/test_nan_safety.py` asserting NaN (not 0.0) for each degenerate case,
  and that a valid input never returns NaN.

## 3. Uncertainty-aware consensus — apply to BOTH families (paper §2.C, Eq. 1)
- Confirm `uNTCP` uses inverse-variance weighting `w_i = 1/σ_i²` over the per-model
  Monte-Carlo variances, with combined variance `1/Σw_i + τ²` where `τ² = Var_i(P_i)` is the
  between-model spread.
- **Add `uTCP`** using the identical machinery over the four TCP models (refactor a shared
  `inverse_variance_consensus(estimates, variances)` helper; uNTCP and uTCP both call it).
- Tests: at a dose where all models agree, consensus variance ≈ min model variance; where
  they diverge, τ² strictly widens the interval.

## 4. Cohort Consistency Score — robust covariance (paper §2.C)
- CCS must use a **robust minimum-covariance-determinant (MCD)** location/scatter
  (`sklearn.covariance.MinCovDet`) for the Mahalanobis reference, not the raw sample
  covariance (raw covariance lets strong outliers mask themselves).
- Flag threshold at the `χ²_{p,0.975}` quantile; expose continuous `CCS = F_{χ²_p}(d_M²)`.
- Test on a synthetic cohort with planted outliers: MCD-CCS recovers them; raw-covariance
  CCS demonstrably under-detects (regression guard).

## 5. Therapeutic index & window + ΔNTCP (paper §2.D) — add if absent
- Add a composite-decision module that, from the consensus curves, returns:
  `UTCP (P+) = uTCP · Π_k(1 − uNTCP_k)`; `therapeutic_index = TD50 / TCD50`;
  `therapeutic_window = {D : uTCP(D) ≥ τ_T and uNTCP(D) ≤ τ_N}` with configurable
  `τ_T`, `τ_N`; each propagating Monte-Carlo uncertainty.
- Add a `delta_ntcp(plan_a, plan_b, threshold)` utility returning per-OAR NTCP change and a
  flag when degradation exceeds `threshold`.
- Tests: TI > 1 for separated curves; empty window when curves overlap; P+ ≤ uTCP.

## 6. Four-tier benchmarking harness (paper §2.E)
- Confirm the harness runs the four model classes under ONE protocol and reports **apparent
  vs cross-validated** AUC per model:
  - T1 literature-fixed classical; T2 MLE refit (bootstrap CI, boundary-convergence flag);
  - T3 multivariable clinical-covariate logistic regression **gated by EPV ≥ 10** with LOO-CV;
  - T4 xAI-ML (XGBoost, RandomForest, ANN) under **stratified group k-fold** (no patient
    leakage), plus SHAP/LIME/PDP-ICE.
- Report AUC, bootstrap Brier, Hosmer–Lemeshow, ECE, calibration slope, and decision-curve
  analysis per model. ML outputs must be returned in separate columns/artifacts — never
  overwriting classical NTCP fields.
- Tests: EPV guard refuses to fit when events/predictor < 10; group k-fold never places the
  same patient in train and test.

## 7. Physics-informed (LQ-constrained) network (paper §2.E, Eq. 2)
- Confirm/implement the loss `L = L_BCE + λ_phys·L_LQ + λ_bc·L_BC`, where `L_LQ` penalises
  departure from LQ dose-response at collocation doses and `L_BC` enforces zero response at
  zero dose and monotonicity.
- It is **research-grade and unvalidated** — guard it behind ADVANCED + an explicit
  `experimental=True` flag, and have it emit a "not for clinical use" notice in outputs/logs.
- Keep `torch` an OPTIONAL dependency; importing the engine without torch must still work.

## 8. Governance enforcement (paper §2.A) — make it testable
- Add `tests/test_governance.py` proving: in BASIC mode no configuration path activates ML
  (attempting `enable_ml=True` without `mode="advanced"` raises or is ignored with a logged
  refusal); unavailable ADVANCED features return NaN/structured "unavailable", not silent
  zeros; switching to ADVANCED adds artifacts **without changing any classical output
  column** (compare BASIC vs ADVANCED classical columns byte-for-byte on a fixture).

## 9. Paper-figure capsule (new, top-level `paper/`)
- Add the provided `paper/reproduce_figures.py`, `paper/requirements.txt`,
  `paper/README.md`, and `paper/data/` (cohort.csv, ground_truth.json).
- Wire the `# ENGINE HOOK` points so that, when rbGyanX is importable, the capsule calls the
  real `rbgyanx_engine` primitives (NTCP, calibration, CCS, harness) instead of the bundled
  reference functions, and prints which path it used. Keep the reference fallback so the
  capsule runs standalone.
- Add a CI job `paper-figures` that runs the capsule and uploads `paper/figures/*.png` as
  build artifacts (so every release ships reproducible figures).

## 10. Docs, changelog, CI
- Update `CHANGELOG.md` with a `## [1.0.0]` entry summarising the above (version SoT,
  NaN-safety tests, uTCP, MCD-CCS, therapeutic index/window, ΔNTCP, governance tests, paper
  capsule).
- Ensure CI matrix stays green: core (no ML deps) + full (optional stack) on
  {ubuntu, windows} × py{3.10,3.11,3.12}; ruff + black + mypy (strict on the radiobiology
  core) + pytest with coverage gate.
- Update `README` feature list and the `docs/` notes to match paper terminology
  (hybrid CDSS; TCP/NTCP/UTCP/uTCP/uNTCP/CCS/therapeutic index & window; four model classes).

## 11. Finish
1. Run `ruff check . && black --check . && mypy <core_pkg> && pytest -q`. All green; report
   the final test count and the skip list (headless-GUI / optional-dep skips are acceptable
   and must be named).
2. Commit in logical chunks with conventional-commit messages; push `release/v1.0.0`; open a
   PR titled `release: v1.0.0 — paper alignment, governance tests, uTCP/MCD-CCS, figure capsule`.
3. After the PR is green, tag and push:
   ```
   git tag -a v1.0.0 -m "rbGyanX v1.0.0"
   git push origin v1.0.0
   ```
   and create the GitHub release from the tag, attaching `paper/figures/*.png`.

**Report back**: the resolved module paths (step 0), the final exact test count, any place
where the existing code conflicted with this spec, and anything you could not implement
without clinical data.
