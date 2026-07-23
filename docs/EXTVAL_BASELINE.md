# External validation — Phase 1 green-baseline record

**Date:** 2026-07-01 · **Branch:** `feat/extval-benchmark` · **Repo state:** working-tree drift reconciled to a single commit.

This file records the verified clean-checkout baseline that all downstream external-validation phases
(`CLAUDE_CODE_EXTVAL_PLAN.md`) build on. Phase 0 data-readiness is in `docs/EXTVAL_DATA_READINESS.md` (verified, not re-derived).

## 1. Install (clean checkout)

```powershell
pip install -e ".[dev]"
```

Result: editable install succeeds; `rbgyanx 1.0.0` registered. (Engine subpackages resolve via `conftest.py` path
fallback; `pip install -e ./engine -e ./engine_advanced -e ./engine_advanced_f` is the reproducible alternative.)

## 2. Test baseline (zero environment variables)

```powershell
python -m pytest --import-mode=importlib -q
```

| Metric | Value |
|--------|-------|
| Passed | **487** |
| Skipped | 3 (GUI headless ×2, optional `validation_utils`) |
| Failed | 0 |
| Exit code | **0** |
| Interpreter | Python 3.14.2, pytest 9.0.2 (local dev, best-effort; CI matrix is 3.10–3.12) |
| Env vars required | **none** |

The count is **identical before and after the Phase-1 lint/type hardening**, confirming the classical radiobiology
numerics are unchanged (do-no-harm contract held — see §4).

> **Note (non-blocking):** without `PYTHONUTF8=1` a background-thread `UnicodeDecodeError (cp1252)` ResourceWarning
> is emitted by one test that reads child-process output; it does **not** fail the run (exit 0). Tracked as a latent
> Windows-encoding robustness item, not a Phase-1 blocker.

## 3. Lint / type gate (Phase-1 scope)

Clean on `engine/radiobiology` + the four new modules (`composite_decision`, `inverse_variance_consensus`,
`validation/cohort_consistency`, `validation/four_tier_harness`):

| Tool | Result |
|------|--------|
| `ruff check` | All checks passed |
| `black --check` | All files unchanged |
| `mypy --follow-imports=silent` | Success, no issues (19 source files) |

`radiobiology.*` is held to strict typing via the `[[tool.mypy.overrides]]` block (`disallow_untyped_defs=true`);
the dead `engine.radiobiology.*` override entry was removed (modules import as `radiobiology.*` under the `src`
layout). A handful of pre-existing typing nits remain in non-target modules outside the do-no-harm core
(`dicom_io/txt_dvh_reader`, `statistical_models/logistic_tcp_mv`, `config/site_params`, `uncertainty/parameter_mc`);
these are out of Phase-1 scope and tracked for later.

## 4. Version single source of truth

All version surfaces reconciled to **1.0.0**:

| Surface | Value |
|---------|-------|
| `engine/rbgyanx_engine/_version.py` (`__version__`) | 1.0.0 |
| `VERSION.txt` | 1.0.0 (release date corrected 2025-12-25 → 2026-06-10) |
| `CITATION.cff` | 1.0.0, `doi: 10.5281/zenodo.20623120` (set this phase) |
| `pyproject.toml` / `engine/pyproject.toml` | 1.0.0 |
| `engine/VERSION` | 0.1.0-alpha → **1.0.0** (stray orphan reconciled) |
| `rbgyanx.__version__` (← engine) / `APP_VERSION` (← VERSION.txt) | 1.0.0 |

`tests/test_version_consistency.py` enforces agreement across `VERSION.txt`, `CITATION.cff`, `pyproject.toml`,
engine `__version__`, and `rbgyanx.__version__`.

## 5. Documentation drift fixed

- Published test count reconciled **462 → 487** (the 462 predated the merged external-validation work) across
  `README.md`, `docs/TEST_RUN_SUMMARY.md`, `docs/VERIFICATION_REPORT.md`, `reproducibility/README_SYNTHETIC.md`.
- `419` (no-optional-deps baseline) vs `487` (full deps) confirmed as two documented scenarios, not a contradiction.

## 6. Phase-1 exit criteria — status

| Criterion | Status |
|-----------|--------|
| Working-tree drift committed; local == GitHub-reconcilable | ✅ (this commit) |
| Single version source | ✅ |
| `CITATION.cff` Zenodo DOI set | ✅ 10.5281/zenodo.20623120 |
| `pip install -e ".[dev]"` + `pytest` green, zero env vars | ✅ 487/3/0, exit 0 |
| ruff + black + mypy clean on engine/radiobiology + new modules | ✅ |
| Classical numerics unchanged (regression contract) | ✅ count identical pre/post |

**Phase 1 complete.** Next: Phase 2 — real DVH + feature front-end (`dicompyler-core` extraction → `cohort_features.csv`).
