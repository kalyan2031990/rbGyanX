# Changelog

## [0.1.0-alpha] — 2026-05-29 (R1)

### Added

- Public package **`rbgyanx-engine`** (`import rbgyanx_engine`) in repo **rbGyanX_cdss**
- Unified API: `run_analysis(RunConfig)` with `endpoint=tcp|ntcp|both`
- Classical **NTCP**: LKB log-logistic, LKB probit, Relative Seriality
- Multi-site NTCP YAML: Brain (GBM/Mets), H&N, Lung, Breast
- DICOM OAR extraction via `get_oar_structures()`
- CLI: `python -m rbgyanx_engine --dicom-dir ... --endpoint both --mode basic`
- Outputs: `ntcp_results.csv`, `provenance.json`, `qa_report.json`

### Changed

- Renamed orchestration package from `py_tcpx` to `rbgyanx_engine` (TCP pipeline retained)

## [1.0.0] — 2026-05-19 (py_tcpx lineage)

### Added

- Unified CLI `python -m py_tcpx` for Phases 1–8
- DICOM RT ingestion (single patient, cohort subfolders, flat multi-patient)
- Commercial TPS DVH text reader (`dicom_io/txt_dvh_reader.py`)
- Classical TCP: Poisson, Zaider–Minerbo, gEUD, logistic
- Parameter Monte Carlo uncertainty and hypoxia correction
- Multivariable logistic TCP (MVL) with EPV guard
- XGBoost and random forest with nested CV
- SHAP, PDP/ICE, calibration and cohort consistency metrics
- Excel benchmarking workbook and publication figures
- Site parameters for Brain, H&N, Lung SBRT, Breast (`config/site_params_default.yaml`)

### Repository

- Release-ready layout: MIT license, `pyproject.toml` entry point, examples docs
- Removed development-only scripts and local machine paths from the codebase
