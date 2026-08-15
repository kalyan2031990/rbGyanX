# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-08-15 — release identifier FINAL_V3.2

Release-repair and freeze. **No scientific result changed**: every headline value was independently
recomputed and matched before this release was built, and nothing was rerun to produce it. Four
release blockers from the final completion audit are closed.

### Added

- **`analysis/` — the code that produced the reported results is now versioned** (blocker B1).
  Eleven analyses across `cohort/`, `radiomics/`, `ibsi/`, `dosiomics/`, `pinn/`, `bayesian/`,
  `ccs/`, `statistics/` and `provenance/`. `analysis/FINAL_ANALYSIS_CODE_MANIFEST.json` maps each
  headline result to its exact script (path + SHA-256 + line count), configuration, input and output
  manifests, random seed, package versions and source commit. Previously the engine was versioned
  but the analysis layer was not, so no commit described how the reported numbers were computed.
- `docs/DOSIOMICS_DATA_PROVENANCE.md` — the real-production-dosiomics vs synthetic-test-data
  distinction, stated explicitly.
- `engine_advanced/tests/test_dosiomics_production_safety.py` — 11 regression tests proving both
  halves of the guard: a missing real dose yields no production dosiomics, and explicit test mode
  still exercises the pipeline.

### Changed

- **Synthetic dose voxels can no longer enter a production dosiomics pathway** (blocker B2).
  `extract_oar_dose_volume()` previously ended in an unconditional
  `return synthetic_oar_dose_voxels(...)`, and the only production caller invoked it with no RTDOSE
  path at all — so every ADVANCED run populated `dosio_*` columns from generated voxels. Those
  surrogates were retracted and underlie no reported result. Now:
  - real RTDOSE is the only production source, resolved by `integration.find_rt_files()`;
  - with no real grid the extractor returns `(None, "NOT_AVAILABLE")` and logs loudly;
  - synthetic output requires an explicit `allow_synthetic=True` that no production path passes;
  - `assert_production_dose_source()` raises `SyntheticDoseInProductionError` for any other source,
    and an omitted `dose_source` is treated as `NOT_AVAILABLE` rather than trusted;
  - NTCP rows carry `dosiomics_status` / `dosiomics_source`, and a patient without a real grid gets
    no `dosio_*` column at all, so a missing measurement is visibly missing.
- `analysis/dosiomics/real_dosiomics.py`: the `--repo` default was an absolute local path; it now
  resolves from the file's own location. Same tree, no behavioural change.
- Version identifiers separated: software semver `1.1.0`, release identifier `FINAL_V3.2`.

### Documentation

- Manuscript B section 3.2: the two `[from manifest]` placeholders resolved to QC_PASSED **219** and
  OUTCOME_LINKED **127**, each cited to its `radiomics_manifest.json` key, with the 219 → 127 drop
  attributed to clinical-data loss rather than imaging QC (blocker B4).
- `docs/AUDIT.md` and `docs/IMPLEMENTATION_ROADMAP.md` corrected: the engine's `dose3d` module
  computes first-order dose features only; the reported 3-D texture dosiomics come from
  `analysis/dosiomics/real_dosiomics.py`.

## [1.0.0] - 2026-08-02

First public, citable release. BASIC (clinic decision-support) and ADVANCED (research)
governance is enforced by the engine; ML/xAI/PINN are ADVANCED-only and experimental.
**Not a regulated medical device.**

### Added

- **PySide6/Qt6 desktop interface** alongside the existing Tkinter app: Workflow, Run
  (live progress), Results (interactive DVH), Visualisation (dose → per-OAR NTCP → P+ Sankey,
  PRISMA-style cohort flow, SHAP/xAI), and an ADVANCED-only, opt-in AI assistant.
- **DVH integrity validator** (`engine/dicom_io/dvh_integrity.py`): every text-DVH ingest is
  sorted by dose and rejected — never silently repaired — if the cumulative curve is inverted,
  non-monotone, duplicated in dose, negative or non-finite. Shipped example DVHs are now a
  positive control for the reader.
- 22 analytic **positive controls** for the corrected NTCP models (`tests/test_ntcp_positive_controls.py`).

### Changed (user-visible behaviour)

- **Relative-seriality NTCP** now complements outside the voxel product
  (`NTCP = 1 − Π_i (1 − P_i^s)^{v_i})^{1/s}`); a prior formulation pinned the value near 1.0.
  Corrected values span a realistic range.
- **Bounded MLE calibration refit**: parameter fits are constrained to physiologic ranges and
  report "not identifiable (flat/degenerate likelihood)" instead of returning extreme values.
- **DVH dose units** are resolved from the file's own declarations (`[Gy]`/`[cGy]`), never guessed
  from magnitude, removing a 100× mis-scaling class of error.
- **NTCP is refused on target volumes.** A PTV/CTV/GTV/ITV/BOOST now returns an explicit
  "not applicable" instead of an NTCP computed from a fallback organ's parameters, and targets are
  excluded from the uncomplicated-control (P+) composition.

### Fixed

- Inverted/scrambled cumulative DVHs were previously accepted silently by the TPS text reader.
- The shipped synthetic demo DVHs are regenerated analytically at 1 Gy resolution as physically
  valid, smooth cumulative curves (clearly labelled SYNTHETIC).

### Notes

- **Do-no-harm:** the classical NTCP/TCP numerics that back the published validation are unchanged
  by the interface and DVH-integrity work (the validator is on the text path only; the validation
  cohorts are extracted from dicompylercore-computed DVHs). Full suite: 763 tests, 0 failures.
- No patient data, cohort tables, or DICOM are included in this repository.

## [Unreleased]

### Added

- TCIA HNSCC external validation acquisition scaffold (`external_validation/`).
- TG-263 structure normalization (`engine/config/tg263_aliases.py`).
- TCIA HNSCC DICOM adapter and clinical covariate mapper.
- External validation pipeline (`engine/validation/hnscc_external_val.py`).
- **Real DVH feature front-end** (`engine/dicom_io/cohort_features.py`) + analytic synthetic
  DICOM-RT factory (`tests/synthetic/dicom_rt_factory.py`); `cohort_features.csv` builder.
- **Four-class external benchmark** (`engine/validation/extval_benchmark.py`): classical,
  clinical, dosiomics ML, and LQ-constrained **PINN** (`engine/validation/outcome_pinn.py`)
  under centre-grouped CV, with AUC/Brier/H-L/ECE/calibration/DCA and optimism plots.
- Benchmark + ablation drivers, synthetic CI mirror (`external_validation/`), `extval` CI job.
- `load_hnscc_outcomes` multi-sheet outcome loader; results in `docs/EXTVAL_RESULTS.md`,
  paper section in `paper/EXTERNAL_VALIDATION.md`.

### Fixed

- Pin `pydicom>=2.4,<3.0` and remove the legacy `dicom` dependency — dicompyler-core 0.5.6
  needs pydicom < 3.0, and the legacy `dicom` package shadowed pydicom, breaking all
  real-DICOM DVH extraction.

## [1.0.0] - 2026-06-10

### Added

- Version single source of truth (`engine/rbgyanx_engine/_version.py`) and `tests/test_version_consistency.py`.
- NaN-safety tests (`tests/test_nan_safety.py`) for all NTCP primitives.
- Inverse-variance consensus (`uncertainty/inverse_variance_consensus.py`) for **uNTCP** and **uTCP**.
- MCD-based Mahalanobis CCS (`validation/cohort_consistency.py`) with raw-covariance regression baseline.
- Composite decision module: therapeutic index/window, P+ (uTCP×Π(1−uNTCP)), `delta_ntcp()`.
- Four-tier benchmarking harness (`validation/four_tier_harness.py`) with EPV guard and group k-fold.
- Governance tests (`tests/test_governance.py`) for BASIC vs ADVANCED ML gating.
- Paper-figure capsule (`paper/`) with CI `paper-figures` artifact job.
- Root `pyproject.toml` workspace, synthetic tests, Zenodo reproducibility packaging.

### Changed

- NTCP primitives return **NaN** (not 0.0) for degenerate/empty inputs.
- PINN training requires `experimental=True` and logs not-for-clinical-use notice.
- `CITATION.cff`, `VERSION.txt`, and `pyproject.toml` aligned to **1.0.0**.

### Fixed

- `code3` clinical `PatientId` column alias.
- TCP mean/range test aggregates all registered TCP models.
