"""
ADVANCED example — research workflow: four-class benchmark on a synthetic cohort.

Demonstrates the pieces a researcher uses, entirely on fabricated data:

  1. generate a synthetic cohort feature table (same schema as the DICOM feature
     front-end, from a known dose->outcome model);
  2. run the leakage-safe four-class benchmark (C1 classical / C2 covariate /
     C3 dosiomics-ML / C4 LQ-PINN) for one endpoint, reporting apparent vs
     cross-validated AUC (the optimism gap);
  3. load a generic clinical-CSV (patient_id + binary endpoint + covariates) with the
     reusable loader — the entry point for running on YOUR data.

ILLUSTRATIVE ONLY: synthetic inputs; the metrics are not validation results.

    python examples/advanced_demo.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd

from validation.clinical_cohort import load_clinical_csv
from validation.extval_benchmark import run_benchmark

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
OUT_DIR = HERE / "output" / "advanced"
FEATURES = OUT_DIR / "cohort_features.csv"
CLINICAL = HERE / "data" / "clinical_cohort.csv"


def _make_synthetic_cohort() -> pd.DataFrame:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            sys.executable,
            str(REPO / "external_validation" / "make_synthetic_mirror.py"),
            "--out",
            str(FEATURES),
            "--n",
            "120",
            "--seed",
            "0",
        ],
        check=True,
    )
    return pd.read_csv(FEATURES)


def main() -> int:
    print("1) Synthetic cohort feature table (no patient data)")
    df = _make_synthetic_cohort()
    print(f"   {len(df)} patients x {df.shape[1]} columns -> {FEATURES}\n")

    print("2) Four-class benchmark - endpoint 'locoregional', dosiomics features")
    table, extras = run_benchmark(
        df, endpoint="locoregional", feature_set="dosiomics", lambda_phys_sweep=(0.0, 1.0), seed=0
    )
    cols = ["tier", "name", "apparent_auc", "cv_auc", "optimism", "brier", "net_benefit"]
    print(f"   n={extras['n']}, events={extras['events']}, features={extras['n_features']}")
    print(table[cols].round(3).to_string(index=False))
    out_csv = OUT_DIR / "benchmark_locoregional.csv"
    table.to_csv(out_csv, index=False)
    print(f"   table -> {out_csv}\n")

    print("3) Generic clinical-CSV loader (run this on YOUR data)")
    cohort = load_clinical_csv(
        CLINICAL, endpoint="xerostomia_grade2", covariate_cols=["age", "sex", "smoker"]
    )
    print(
        f"   {CLINICAL.name}: n={cohort.n}, events={cohort.n_events}, "
        f"event_rate={cohort.event_rate:.2f}, covariates={cohort.covariates}"
    )
    print("\nNote: illustrative synthetic data - not clinical or validation results.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
