# `analysis/` — the code that produced the reported results

This directory closes audit blocker **B1**. Until now the engine was versioned but the analysis layer
that consumed it was not, so no commit described how the reported numbers were computed. Every script
here is the exact one that produced a final headline result.

**Nothing was rerun to create this directory.** The outputs were generated earlier and independently
verified; `FINAL_ANALYSIS_CODE_MANIFEST.json` records their SHA-256 hashes rather than regenerating
them.

## Layout

| Directory | Produces |
|---|---|
| `cohort/` | the locked cohorts: DICOM indexing, UID linkage, clinical linkage, eligibility waterfall, patient feature tables |
| `radiomics/` | CT radiomics extraction (219 patients, 1 515 QC-passed features), shard assembly, V2→V3 regression proof |
| `ibsi/` | IBSI-1 digital-phantom benchmark (56/63) |
| `dosiomics/` | real 3-D dosiomics from RTDOSE grids (186 patients, 735 features) |
| `pinn/` | hybrid physics+residual PINN, comparator models, XAI, ablation |
| `bayesian/` | PyMC NUTS posterior inference for the LKB parameters |
| `ccs/` | Cohort Consistency Score, variants A and B |
| `statistics/` | feature-family model comparison, the 222-test statistical analysis, machine-readable outputs, manuscript numerical consistency |
| `provenance/` | pre-upgrade baseline capture and the final deliverable/diff generator |
| `scripts/` | earlier consensus and correctness-curve analyses (pre-existing, unchanged) |

## Manifest

`FINAL_ANALYSIS_CODE_MANIFEST.json` has one entry per analysis carrying `analysis_name`,
`headline_results`, `script` (path + SHA-256 + line count), `config`, `input_manifest`,
`output_manifest`, `software_version`, `python_version`, `package_versions`, `random_seed`,
`source_commit` and `result_files` (path + SHA-256 + size).

Eleven analyses; all scripts present; all referenced result files present and hashed.

## What is *not* here, and why

**Inputs and outputs.** `analysis/.gitignore` excludes `inputs/`, `outputs/` and `*.dcm`. The cohorts
are identifiable and the pseudonym maps are held outside the repository (constraint C2). The results
live in `rbGyanX_Manuscript_Workspace/`, which the manifest references by relative path and hash.

**Raw TCIA/SPARK source data.** Not redistributable here.

## Seeds and determinism

Seed 0 throughout, with derived per-repeat seeds (`seed + 100*repeat`) so the repeated CV partitions
are distinct but reproducible. Extraction steps (radiomics, dosiomics, IBSI, linkage) have no
stochastic component and are marked `not applicable` rather than given a meaningless seed.

Repeat runs produced 16/16 byte-identical outputs.

## Environment

Python 3.14.2 — numpy 2.4.0, scipy 1.16.3, pandas 2.3.3, scikit-learn 1.8.0, torch 2.12.0+cpu,
PyMC 6.2.0, ArviZ 1.2.0, PyTensor 3.2.4, numba 0.66.0, pydicom 2.4.5, scikit-image 0.26.0,
statsmodels 0.14.6. Exact versions per analysis are in the manifest.

pyradiomics does not build on Python 3.14, so CT radiomics and dosiomics use the in-house
IBSI-aligned engine. That engine is benchmarked against the IBSI-1 digital phantom at 56/63 features;
**IBSI compliance is not claimed**. See `03_RADIOMICS/IBSI/IBSI_BENCHMARK_REPORT.md`.

## One modification on import

`dosiomics/real_dosiomics.py` had an absolute local path as the `--repo` default. It now resolves from
the file's own location. No other change was made to any script, and the default resolves to the same
tree that produced the reported run.
