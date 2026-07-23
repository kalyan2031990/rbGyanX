# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

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
