# rbGyanX — software baseline (Track A)

Snapshot of the green baseline for the public, reusable rbGyanX tool. Records what "clean" means for
the codebase, independent of any validation study or dataset. Covers Track-A phases A1–A4.

_Last established: 2026-07-18 · branch `feat/extval-benchmark`._

## Test suite

| Metric | Value |
| --- | --- |
| Test files | 71 |
| Tests collected | 540 |
| Failed | 0 |
| Skipped | 2–3 (optional-dependency guards) |

Full local run (`pytest`, all default `testpaths`) is green with **zero environment variables** set.
Skips are `pytest.importorskip` / marker guards for optional stacks (ML / torch / pymc / DICOM fixtures),
not failures.

```
pytest --import-mode=importlib
```

## Coverage gate

| Scope | Coverage | Gate | Where |
| --- | --- | --- | --- |
| `engine/radiobiology` (validated numerics) | 86% | ≥70% | CI `core` job (no-ML matrix) |
| `engine` (whole maintained package) | 73% | ≥70% | CI `full` job (optional stack) |

Coverage is deliberately **not** gated over the legacy top-level scripts / GUI, which are kept for
provenance and not exercised by the data-independent suite.

## Lint / type / format gate

The enforced gate is **scoped to the maintained modules** (mirrors `.github/workflows/ci.yml`), not the
legacy top-level scripts (`code1..7_*.py`, `rbgyanx_gui.py`, the root `*_qa_test_suite.py`), which are kept
for provenance and intentionally excluded from linting.

| Tool | Scope | Status |
| --- | --- | --- |
| ruff | `engine/radiobiology`, `tests/synthetic`, extval modules, NTCP anchors | clean |
| black `--check` | same scope | clean |
| mypy | `engine/radiobiology` (`--config-file pyproject.toml`) | clean (16 source files) |

CI enforces this scope on Python 3.10 / 3.11 / 3.12 across Ubuntu + Windows (core job), plus a full-stack
job. Local dev interpreter here is Python 3.14; supported/tested runtimes are 3.10–3.12.

## Version single-source of truth

Canonical version literal: **`engine/rbgyanx_engine/_version.py`** (`__version__ = "1.0.0"`).

- `engine/pyproject.toml` — **dynamic**, resolved via `[tool.setuptools.dynamic] version = {attr = "rbgyanx_engine._version.__version__"}`.
- `rbgyanx_engine.__version__` and `rbgyanx.__version__` both derive from it at runtime.
- `pyproject.toml` (root), `VERSION.txt`, `CITATION.cff` carry the string statically and are **guarded**
  against drift by `tests/test_version_consistency.py` (fails the build if any diverges).

To bump the release version: edit `_version.py`, then update the three guarded files to match.

## Dependency hygiene

- **`pydicom` pinned `<3.0`** everywhere: root `pyproject.toml`, `engine/pyproject.toml`, and
  `requirements-lock.txt` (`pydicom==2.4.4`). pydicom 3.x removes `pydicom.pixel_data_handlers`, which
  `dicompyler-core` 0.5.6 imports — so 3.x breaks the real-DICOM path.
- The legacy **`dicom`** PyPI package (`dicom==0.9.9.post1`) has been removed from the lock file; it must
  never be installed alongside `pydicom`.
- `requirements-lock.txt` re-encoded from UTF-16 to **UTF-8 / LF**.

## Repository hygiene

- `.gitattributes` added: `* text=auto eol=lf` (LF-normalised text; `*.ps1/.bat/.cmd` keep CRLF; known
  binaries marked `binary`). Kills cross-platform CRLF churn.
- No `__pycache__/`, `*.pyc`, or `*.egg-info/` tracked (all covered by `.gitignore`).
- `CITATION.cff` DOI = `10.5281/zenodo.21757164`.
- Track-B validation-study planning docs (private local data paths / cohort design) are `.gitignore`d out
  of the public repo history — kept on disk only.

## Reusable interfaces (A2) — no study coupling

The tool runs on **any** user's data through three input paths, all synthetic-tested:

- **DICOM RT** (`--dicom-dir`) — RTSTRUCT + RTDOSE (+ optional RTPLAN); names normalised via the
  TG-263 / alias map (arbitrary/centre spellings, e.g. `Rectum_P` → `Rectum`).
- **DVH text** (`--dvh-dir`) — Eclipse / RayStation / Pinnacle exports, cGy or Gy.
- **Generic clinical-CSV** — `validation.clinical_cohort.load_clinical_csv` (patient_id, binary
  endpoint[0/1], optional covariates) with strict validation.

The feature front-end (`cohort_features`) takes a configurable `OARSpec` set (default = head & neck;
`PROSTATE_OAR_SPECS` shipped as a non-HN example); the benchmark is endpoint-agnostic and auto-discovers
any site's OAR features. See `tests/test_reusable_interfaces.py`.

## Input-validation robustness (A4)

Malformed / incomplete input fails fast with an actionable message rather than a silent NaN:

- DVH: missing directory, no files matching the glob, no data rows, zero differential volume.
- DICOM: missing folder, missing required modalities, empty RTSTRUCT (no ROIs).
- Missing structures: `dicom_io.input_validation.ensure_targets_present` errors when no target volume
  is found. See `tests/test_input_validation.py`.

## Synthetic examples (A3)

`examples/` ships a tiny **synthetic, illustrative** dataset + `basic_demo.py` (clinic: engine → TCP/NTCP)
and `advanced_demo.py` (research: synthetic cohort → four-class benchmark + generic CSV loader), with a
quickstart README. PHI-free, CI-smoke-tested, never presented as validation. `examples/output/` is ignored.

## Reproduce this baseline

```bash
# from a clean checkout
pip install -e "./engine" -e "./engine_advanced" -e "./engine_advanced_f" -e ".[dev]"
pytest --import-mode=importlib -q
ruff check engine/radiobiology engine/tests/test_ntcp_scientific_anchors.py tests/synthetic
black --check engine/radiobiology engine/tests/test_ntcp_scientific_anchors.py tests/synthetic
mypy engine/radiobiology --config-file pyproject.toml
```
