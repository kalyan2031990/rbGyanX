# rbGyanX — radiobiology-guided clinical decision **support**

[![CI](https://github.com/kalyan2031990/rbGyanX/actions/workflows/ci.yml/badge.svg)](https://github.com/kalyan2031990/rbGyanX/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10--3.12-blue.svg)](pyproject.toml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.21757163-blue.svg)](https://doi.org/10.5281/zenodo.21757163)

rbGyanX evaluates radiotherapy treatment plans using transparent, classical radiobiology. Given
dose–volume histograms — from DICOM RTDOSE/RTSTRUCT or planning-system text exports — it computes
tumour control probability (**TCP**), normal-tissue complication probability (**NTCP**: LKB probit,
LKB log-logistic, relative seriality), uncomplicated control (**P+**), an uncertainty-aware
consensus, and QUANTEC flags, behind a four-tier validation harness.

It is written for **medical physicists and radiobiology researchers** who need a number they can
trace back to an equation, a parameter set, and the commit that produced it.

---

## What this is not for

Read this before installing.

- **It is not a medical device**, and not certified as one under any regulatory regime. It does not
  diagnose, treat, prescribe, or rank treatment options.
- **It does not make decisions.** It computes model outputs and shows you the assumptions behind
  them. Every clinical judgement remains the treating team's.
- **It is not a validated dose-escalation or plan-acceptance tool.** The shipped QUANTEC reference
  values are single-organ constraints under conventional fractionation. They do not compose, and
  they do not apply to SBRT, re-irradiation, or paediatric cases.
- **Its model outputs are not equally trustworthy.** Poisson TCP saturates at cohort dose levels;
  lung-SBRT TCP uses conventional-fractionation parameters; reported uncertainty is parameter
  uncertainty only. These are stated individually in
  [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md), which is worth reading in full before
  you quote any output.

If you need a regulated planning or QA system, this is not that. If you need to understand *why* a
radiobiological model produced a number, that is what this is for.

See [`DISCLAIMER.md`](DISCLAIMER.md) for the complete statement.

---

## Install

Python **3.10–3.12** — exactly the matrix CI tests, on Linux and Windows. 3.13+ is untested and so
unsupported; the dependencies resolve there, but nobody has verified the numerics.

From a clone (the usual route, and what the quickstart below assumes):

```bash
git clone https://github.com/kalyan2031990/rbGyanX && cd rbGyanX
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e "./engine" -e ".[dev,ml]"          # add ,qt for the Qt6 desktop app
```

Or from the release assets — **both wheels together**, because `rbgyanx` imports `rbgyanx_engine`
at module scope and the engine is published as a release asset rather than on PyPI:

```bash
pip install rbgyanx_engine-1.3.0-py3-none-any.whl rbgyanx-1.3.0-py3-none-any.whl
```

Installing only the `rbgyanx` wheel fails at install time with an unresolved `rbgyanx-engine`
requirement. That is deliberate: through v1.2.1 the dependency was undeclared, so the wheel
installed cleanly and then raised `ModuleNotFoundError` on `import rbgyanx`.

> **On the analysis environment.** `analysis/FINAL_ANALYSIS_CODE_MANIFEST.json` records Python
> 3.14.2 on Windows with its own package set. That is not a contradiction of the range above: the
> published analysis drove the engine directly rather than this installed distribution. It is
> historical provenance for the reported numbers and is deliberately not edited to match.

---

## 60-second example

Synthetic data, shipped in the repository. No patient data is required or included. Run it from
the root of a clone — it reads `examples/data/dvh_txt`, which ships in the repository rather than
inside the wheel.

```bash
python - <<'PY'
from pathlib import Path
from rbgyanx.services.run_controller import RunController
from rbgyanx.services.run_request import RunRequest

req = RunRequest(analysis_mode="NTCP", input_path=Path("examples/data/dvh_txt"),
                 output_dir=Path("."), input_source="dvh_txt")
res = RunController().run_dvh_text(
    req, ntcp_models={"LKB": {"model": "lkb_probit", "params": {"TD50_gy": 39.9, "m": 0.40}}})

# Check res.ok before reading results. A run that could not start returns ok=False with the
# reason in res.errors and an empty res.structures, so a snippet that iterates straight into
# res.structures prints nothing at all and is indistinguishable from success.
if not res.ok:
    raise SystemExit("run failed: " + "; ".join(res.errors))

for s in res.structures:
    tag = "target — NTCP n/a" if getattr(s, "is_target", False) else f"NTCP={s.ntcp}"
    print(f"{s.patient_id} {s.label:12s} Dmean={s.mean_dose_gy:5.1f} Gy  {tag}")
PY
```

Expected output, four patients by four structures:

```
EX-001 PTV70        Dmean= 71.5 Gy  target — NTCP n/a
EX-001 Parotid_L    Dmean= 24.1 Gy  NTCP={'LKB': 0.16109318465827}
EX-001 Parotid_R    Dmean= 22.2 Gy  NTCP={'LKB': 0.13344012283792178}
EX-001 SpinalCord   Dmean= 17.3 Gy  NTCP={'LKB': 0.0787494101410367}
...
```

`RunController` is the supported programmatic entry point, and is what both desktop apps call.

Desktop: `python -m rbgyanx.qtapp` (Qt6, needs the `qt` extra) or `python rbgyanx_gui.py`
(the original Tkinter app).

---

## Verify

```bash
pytest -q
```

Measured on Linux, Python 3.11, in two configurations:

| Installed | Result |
|---|---|
| `.[dev,ml]` + engine | **1351 passed, 24 skipped, 0 failed** |
| the above + `.[qt]` (PySide6, plotly) | **1425 passed, 19 skipped, 1 failed** |

Your numbers will differ, because whole modules skip when an optional dependency is absent. Run
`pytest -rs` to see exactly what skipped and why.

**The one failure is environmental, and expected in a container.**
`tests/test_qtapp_smoke.py::test_selftest_renders_plotly_in_a_live_webengine` drives a real
`QWebEngineView`, loads an interactive Plotly DVH into it, and queries the rendered DOM to confirm
the plot actually drew — it exists to catch a blank-plot packaging bug at source level. It needs a
working OpenGL backend. In a headless container Chromium starts but reports
`Failed to create RHI for backend: OpenGL`, the plot does not draw, and the test correctly says
so. It has deliberately **not** been softened into a skip: a guard loose enough to pass here would
also pass on the broken packaging it was written to catch.

To run the Qt tests at all in a headless environment you need the system Qt libraries (`libegl1`,
`libgl1`, `libxkbcommon0`, `libdbus-1-3`, `libfontconfig1` on Debian/Ubuntu — pip does not install
these), plus `QT_QPA_PLATFORM=offscreen` and `QTWEBENGINE_DISABLE_SANDBOX=1`.

Other skips: the live AI-provider tests are opt-in behind `RBGYANX_LIVE_LLM_TEST=1`, and
`tests/test_with_real_data.py` skips unless a real cohort is present. **No test requires patient
data.**

The scientific core is pinned by **22 analytic positive controls**
(`pytest tests/test_ntcp_positive_controls.py`): NTCP = 0.5 at TD50, monotonicity, QUANTEC
anchors, and exact UTCP factorisation.

Those 22 are collected test *cases* from 12 test functions — three are parametrised, over four
TD50 values for probit, four for log-logistic, and five seriality values for relative seriality.
Counting `def test_` lines gives 12 and counting controls gives 22; both describe the same file.
`tests/test_version_consistency.py` computes the number from the module and fails if any document
disagrees with it.

CI additionally runs ruff over the whole maintained tree, black and mypy on the numeric core, and
**bandit and pip-audit as blocking gates**. Accepted findings are enumerated with reasons in
[`SECURITY.md`](SECURITY.md); nothing is suppressed for convenience.

---

## Two governed modes

The engine enforces a **BASIC / ADVANCED** split (`rbgyanx.logic.mode_controller`):

- **BASIC (clinic)** — one well-understood NTCP model per site, no ML, no experimental features. A
  small, auditable decision-support surface.
- **ADVANCED (research)** — additional NTCP models, dosiomics/ML, SHAP explainability, a PINN
  benchmark, and an opt-in AI assistant. Everything here is labelled **experimental**.

The mode is a capability gate enforced in code, not a cosmetic toggle: BASIC cannot reach the
experimental paths.

---

## AI assistant (experimental, off by default)

ADVANCED-only, opt-in, and absent entirely in BASIC. It **explains** outputs the engine has
already produced; it never computes or adjusts a TCP/NTCP/UTCP value, and it cannot modify the
numeric core, the tests that verify it, or its own guards.

**The PHI guard fails closed.** Every outgoing message is scanned — system messages and attached
run context included — and if anything is flagged while a **remote** provider is selected, the
send is refused before the network is touched. There is no override: no button, no environment
variable, no config field. A local (loopback) provider only warns, because nothing leaves the
machine. Enforced in `rbgyanx/ai/llm_client.py`, asserted in `tests/test_ai_phi_failclosed.py`
against a transport that records every call.

It is a pattern matcher, not a proof. It cannot recognise a patient described in prose. **Use the
Local provider for anything patient-identifiable** — the block is a backstop for mistakes.

Institutions can remove every remote provider, unrepealably from the interface:

```bash
RBGYANX_AI_DISABLE_REMOTE=1     # or ai.disable_remote: true in a site config file
```

Before running against real cohorts on a remote provider, read
[`docs/RUNNING_WITH_A_REMOTE_PROVIDER.md`](docs/RUNNING_WITH_A_REMOTE_PROVIDER.md) and check what
is granted with `python scripts/ai_capability_report.py --provider kimi`. Full design, capability
matrix and threat model: [`docs/AI_ASSISTANT_DESIGN.md`](docs/AI_ASSISTANT_DESIGN.md).

---

## Documentation

Start here:

| Document | What it answers |
|---|---|
| [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) | **What this release gets wrong or cannot do.** Read before quoting any output. |
| [`DISCLAIMER.md`](DISCLAIMER.md) | The complete not-a-medical-device statement |
| [`docs/TECHNICAL_DEVELOPMENT_NOTE.md`](docs/TECHNICAL_DEVELOPMENT_NOTE.md) | Models, parameters, and design rationale |
| [`docs/RBGYANX_1.0_DESKTOP.md`](docs/RBGYANX_1.0_DESKTOP.md) | Desktop feature guide |
| [`analysis/README.md`](analysis/README.md) | Which script produced which reported number |
| [`DATA_AVAILABILITY.md`](DATA_AVAILABILITY.md) | What is and is not distributed, and how to obtain the cohorts |
| [`docs/EXTVAL_RESULTS.md`](docs/EXTVAL_RESULTS.md) | External-validation benchmark: methods, seeds, tables |
| [`docs/DOSIOMICS_DATA_PROVENANCE.md`](docs/DOSIOMICS_DATA_PROVENANCE.md) | Real production dosiomics vs synthetic test data |
| [`SECURITY.md`](SECURITY.md) | Reporting a vulnerability; accepted audit findings |
| [`CHANGELOG.md`](CHANGELOG.md) · [`CONTRIBUTING.md`](CONTRIBUTING.md) | Release history; how to contribute |

---

## Repository layout

| Path | Role |
|------|------|
| `engine/` | `rbgyanx-engine` — the core: TCP/NTCP, DICOM/DVH I/O, validation, reporting |
| `rbgyanx/` | mode governance, headless services, Qt6 desktop app (`rbgyanx.qtapp`), AI panel |
| `rbgyanx_gui.py` | the original Tkinter desktop app |
| `engine_advanced/`, `engine_advanced_f/` | ADVANCED research modules (dosiomics, PINN, Bayesian NTCP) |
| `analysis/` | the versioned scripts that produced every reported result, with per-analysis provenance in [`FINAL_ANALYSIS_CODE_MANIFEST.json`](analysis/FINAL_ANALYSIS_CODE_MANIFEST.json). Frozen: excluded from linting because its scripts are pinned by SHA-256 |
| `examples/` | shipped **synthetic** demo DVHs — a positive control for the reader |
| `packaging/` | PyInstaller + Inno Setup build scripts |
| `legacy/` | quarantined earlier scripts, retained for provenance and never imported |

**No patient DICOM, cohort tables, or clinical files are in this repository.** External validation
runs on real head-and-neck anatomy (TCIA Head-Neck-PET-CT) *outside* this repo; CI exercises a
synthetic mirror only.

---

## How to cite

Cite the archived release via its **concept DOI**, which always resolves to the newest version —
see [`CITATION.cff`](CITATION.cff), or:

> Mondal, K., Mandal, A., & Vijay, A. *rbGyanX: A radiobiology-guided clinical decision support
> framework* (v1.3.0). Zenodo. https://doi.org/10.5281/zenodo.21757163

The accompanying manuscript will be added as the preferred citation on acceptance.

---

## Licence

[MIT](LICENSE). Research and decision-**support** software — not a regulated medical device.
