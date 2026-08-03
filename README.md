# rbGyanX — radiobiology-guided clinical decision **support**

[![CI](https://github.com/kalyan2031990/rbGyanX/actions/workflows/ci.yml/badge.svg)](https://github.com/kalyan2031990/rbGyanX/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](pyproject.toml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21757164-blue.svg)](https://doi.org/10.5281/zenodo.21757164)

**rbGyanX** evaluates radiotherapy treatment plans with transparent, classical radiobiology —
tumour control (**TCP**), normal-tissue complication (**NTCP**: LKB probit / log-logistic and
relative-seriality), uncomplicated control (**P+**), an uncertainty-aware consensus, QUANTEC
flags, and a four-tier validation harness. It is built for **medical physicists and radiobiology
researchers** who need results they can trace to an equation.

> ⚠️ **Not a medical device.** rbGyanX is decision-*support* and research software. It does not
> diagnose, treat, or prescribe, and it is not a substitute for clinical judgement. See
> [`DISCLAIMER.md`](DISCLAIMER.md).

## Two governed modes

The engine enforces a **BASIC / ADVANCED** split (`rbgyanx.logic.mode_controller`):

- **BASIC (clinic):** one well-understood NTCP model per site, no ML, no experimental features —
  a small, auditable decision-support surface.
- **ADVANCED (research):** additional NTCP models, dosiomics/ML, SHAP explainability, a PINN
  benchmark, and an opt-in AI assistant. Everything here is labelled **experimental**.

Machine learning, xAI and PINN are ADVANCED-only. The mode is a capability gate, not a cosmetic
toggle: BASIC cannot reach the experimental code paths.

## Install

Python **3.10–3.12**. From a clone:

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e "./engine" -e ".[dev]"             # add ,qt for the desktop GUI, ,ml for the research stack
```

## 5-minute example (shipped synthetic data — no patient data)

```bash
python - <<'PY'
from pathlib import Path
from rbgyanx.services.run_controller import RunController
from rbgyanx.services.run_request import RunRequest

req = RunRequest(analysis_mode="NTCP", input_path=Path("examples/data/dvh_txt"),
                 output_dir=Path("."), input_source="dvh_txt")
res = RunController().run_dvh_text(
    req, ntcp_models={"LKB": {"model": "lkb_probit", "params": {"TD50_gy": 39.9, "m": 0.40}}})
for s in res.structures:
    tag = "target — NTCP n/a" if getattr(s, "is_target", False) else f"NTCP={s.ntcp}"
    print(f"{s.patient_id} {s.label:12s} Dmean={s.mean_dose_gy:5.1f} Gy  {tag}")
PY
```

Desktop GUIs: `python -m rbgyanx.qtapp` (Qt6, needs the `qt` extra) or `python rbgyanx_gui.py`
(Tkinter).

## Verify (763 tests, synthetic data only)

```bash
pytest -q
```

The scientific core is pinned by **22 analytic positive controls**
(`pytest tests/test_ntcp_positive_controls.py`): NTCP = 0.5 at TD50, monotonicity, QUANTEC
anchors, and UTCP factorisation. No patient data is required or included.

## How to cite

Cite the archived release via its DOI — see [`CITATION.cff`](CITATION.cff), or:

> Mondal, K., Mandal, A., & Vijay, A. *rbGyanX: A radiobiology-guided clinical decision support
> framework* (v1.0.0). Zenodo. https://doi.org/10.5281/zenodo.21757164

The accompanying manuscript will be added as the preferred citation on acceptance.

## Layout

| Path | Role |
|------|------|
| `engine/` | `rbgyanx-engine` — clinic core: TCP/NTCP, DICOM/DVH I/O, validation, reporting |
| `rbgyanx/` | mode governance, headless services, Qt6 desktop app (`rbgyanx.qtapp`), AI panel |
| `rbgyanx_gui.py` | the original Tkinter desktop app |
| `engine_advanced/`, `engine_advanced_f/` | ADVANCED research modules (dosiomics, PINN, Bayesian NTCP) |
| `examples/` | shipped **synthetic** demo DVHs (a positive control for the reader) |
| `packaging/` | PyInstaller + Inno Setup build scripts |
| `legacy/` | quarantined earlier scripts, kept for provenance |

**No patient DICOM, cohort tables, or clinical files are in this repository.** The external
validation runs on real head-and-neck anatomy (TCIA Head-Neck-PET-CT) *outside* this repo; CI
exercises a synthetic mirror only. Requires `pydicom<3.0`.

## More

- [`docs/EXTVAL_RESULTS.md`](docs/EXTVAL_RESULTS.md) — external-validation benchmark (methods, seeds, tables)
- [`docs/RBGYANX_1.0_DESKTOP.md`](docs/RBGYANX_1.0_DESKTOP.md) — desktop feature guide
- [`CHANGELOG.md`](CHANGELOG.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) · [`SECURITY.md`](SECURITY.md)

MIT License. Decision-support and research software — not a regulated medical device.
