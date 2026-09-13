# External-validation reproduction capsule

Two ways to run the full four-class benchmark (classical vs clinical vs dosiomics vs PINN):
from real TCIA data (requires the licensed archive) or from a fully synthetic mirror (no data
needed — this is what CI runs).

## A. Synthetic mirror (no data, CI-equivalent)

```powershell
python external_validation/make_synthetic_mirror.py --out mirror/cohort_features.csv --n 120 --seed 0
python external_validation/run_benchmark.py --features mirror/cohort_features.csv --out-dir mirror/benchmark --quick --seed 0
```

Outputs: `benchmark_locoregional_dosiomics.csv`, `optimism_locoregional.png`,
`benchmark_results.json`. The `extval` CI job runs exactly this.

## B. Real TCIA cohort (reference-planned dose)

Requires the TCIA Head-Neck-PET-CT archive + clinical workbook (not redistributed here).

```powershell
# 1. Feature table (reads RTSTRUCT+RTDOSE from the zip; CT skipped; plan-sum dose selected)
python external_validation/build_cohort_features.py `
  --zip ".../HNSCC/Radiotherapy_HaN_Lung_AIRTP/HaN/TCIA2_Head-Neck-PET-CT.zip" `
  --clinical ".../clinical_demographic_data/Head-Neck-PET-CT.xlsx" `
  --out external_validation/data/cohort_features.csv

# 2. Benchmark (C1-C4, centre-grouped CV, optimism plots)
python external_validation/run_benchmark.py `
  --features external_validation/data/cohort_features.csv --out-dir external_validation/data/benchmark --seed 0

# 3. Ablations (N-subsampling curve, MCD cohort-consistency)
python external_validation/run_phase4_analysis.py `
  --features external_validation/data/cohort_features.csv --out-dir external_validation/data/benchmark --seed 0
```

`external_validation/data/` is gitignored: **no patient DICOM and no derived real-cohort
table is committed.** Results and framing (reference-dose caveat, small N) are in
`docs/EXTVAL_RESULTS.md`; the paper section is `paper/EXTERNAL_VALIDATION.md`.

## Requirements

`pip install -e "./engine" -e ".[dev,ml,torch]"` (torch is needed only for the C4 PINN;
the PINN is skipped gracefully if torch is absent). Note **pydicom must be < 3.0**
(dicompyler-core requirement); do **not** install the legacy `dicom` package.
```
