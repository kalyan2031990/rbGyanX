# rbGyanX examples (synthetic, illustrative)

Runnable, end-to-end demos on **fabricated synthetic data** — no patient data required.
They exist to show how to install rbGyanX and drive it on *your own* data.

> **⚠ Illustrative only.** Every input under `examples/data/` is generated from a simple
> model (see [`make_example_data.py`](make_example_data.py)). The outputs demonstrate the
> software; they are **not** clinical findings and **not** a validation study. Never cite
> example numbers as results.

## Install

```bash
pip install -e "./engine" -e "./engine_advanced" -e "./engine_advanced_f" -e ".[dev]"
# core-only (no optional ML) is enough for the BASIC demo:
#   pip install -e "./engine" -e ".[dev]"
```

## Generate the tiny synthetic dataset

```bash
python examples/make_example_data.py
```

Writes to `examples/data/`:

| File | Format | Purpose |
| --- | --- | --- |
| `dvh_txt/<PID>_<Structure>_dvh.txt` | Eclipse-style DVH text | 4 synthetic patients (PTV70 + parotids + cord) |
| `clinical_cohort.csv` | generic clinical-CSV | `patient_id`, binary endpoint, covariates |

## BASIC vs ADVANCED

| | BASIC (clinic) | ADVANCED (research) |
| --- | --- | --- |
| Script | [`basic_demo.py`](basic_demo.py) | [`advanced_demo.py`](advanced_demo.py) |
| Input | DVH text folder | synthetic cohort feature table + clinical-CSV |
| Does | runs the engine → per-structure **TCP/NTCP** report | runs the leakage-safe **four-class benchmark** (C1 classical / C2 covariate / C3 dosiomics-ML / C4 LQ-PINN) and the generic CSV loader |
| Needs | core install (`--no-ml`) | optional ML/torch stack |

```bash
python examples/basic_demo.py       # -> examples/output/basic/
python examples/advanced_demo.py    # -> examples/output/advanced/
```

## The three input formats

rbGyanX is dataset-agnostic. Any user runs it through one of three input paths:

1. **DICOM RT** (`--dicom-dir`) — a folder with RTSTRUCT + RTDOSE (+ optional RTPLAN).
   Structures are normalised via the TG-263 / alias map (e.g. `Rectum_P` → `Rectum`).

   ```bash
   python -m rbgyanx_engine --dicom-dir /your/dicom --site PROSTATE --output-dir out/
   ```

2. **DVH text** (`--dvh-dir`) — TPS DVH exports (Eclipse / RayStation / Pinnacle-style,
   cGy or Gy), one `Structure:` block per file, grouped by `Patient ID`.

   ```bash
   python -m rbgyanx_engine --dvh-dir /your/dvh_folder --dvh-glob "*.txt" --output-dir out/
   ```

3. **Generic clinical-CSV** — `patient_id`, a binary `endpoint` (0/1, or yes/no), and any
   covariates. Loaded and validated by
   [`validation.clinical_cohort.load_clinical_csv`](../engine/validation/clinical_cohort.py):

   ```python
   from validation.clinical_cohort import load_clinical_csv
   cohort = load_clinical_csv("your_outcomes.csv", endpoint="toxicity",
                              covariate_cols=["age", "sex"])
   print(cohort.n, cohort.n_events)
   ```

## Outputs

- **BASIC** (`examples/output/basic/`): `tcp_benchmarking.xlsx` (TCP per structure/model),
  `site_detection.csv`, `qa_report.json`, `provenance.json`.
- **ADVANCED** (`examples/output/advanced/`): `cohort_features.csv` (synthetic), the
  benchmark table `benchmark_locoregional.csv`, and optimism/calibration plots.

`examples/output/` is git-ignored; the shipped `examples/data/` is synthetic and safe to
commit.
