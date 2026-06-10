# Changelog

All notable changes to this project are documented in this file.

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [1.0.0] - 2026-06-08

### Added

- Root `pyproject.toml` workspace with dev/lint/test tooling.
- GitHub Actions CI (core + full optional-dependency jobs).
- Synthetic test package under `tests/synthetic/`.
- Automated validation script and real-data technical note section.
- RS parametrisation documentation (`docs/RS_PARAMETRISATION.md`).

### Changed

- NTCP primitives return **NaN** (not 0.0) for degenerate/empty inputs.
- `test_with_real_data.py` uses `input_folders` clinical path.
- Engine ML dependencies moved to optional `[ml]` extra.

### Fixed

- `code3` clinical `PatientId` column alias.
- `synthetic_data` import via editable engine install.
