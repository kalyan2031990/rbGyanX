"""
Generate a synthetic mirror of cohort_features.csv for CI / reproduction.

Emits a table with the SAME schema as the real Phase-2 output but from a known
generative model (dose-driven loco-regional / death endpoints), so the Phase-3/4
benchmark and ablations can run end-to-end **without any patient data**. Used by
the CI job and by anyone reproducing the pipeline offline.

Usage:
    python external_validation/make_synthetic_mirror.py --out <path.csv> [--n 120] [--seed 0]
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

_OARS = ("PharynxConstrictor", "Larynx", "OralCavity", "Parotids", "Submandibular", "SpinalCord")


def make_synthetic_cohort(n: int = 120, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    centre = rng.choice(["A", "B", "C", "D"], size=n, p=[0.37, 0.31, 0.24, 0.08])
    n_fx = 35
    eqd2 = rng.normal(70, 3.5, n).clip(55, 82)
    dmean = eqd2 + rng.normal(1.5, 1.0, n)
    geud = eqd2 - rng.uniform(0, 2, n)
    hi = rng.uniform(0.03, 0.16, n)
    dpf = dmean / n_fx
    bed = dmean * (1 + dpf / 10.0)
    age = rng.uniform(45, 85, n)
    hpv = rng.choice(["positive", "negative", None], size=n, p=[0.35, 0.4, 0.25])

    df = pd.DataFrame(
        {
            "patient_id": [f"SYN-{i:03d}" for i in range(n)],
            "centre": centre,
            "prescription_dose_gy": 70.0,
            "n_fractions": n_fx,
            "approval_status": "SYNTHETIC",
            "dose_summation_type": "PLAN",
            "n_targets": 3,
            "n_oars_mapped": 16,
            "PTV_name": "PTV70",
            "PTV_volume_cc": rng.uniform(80, 300, n),
            "PTV_D95_gy": eqd2 - rng.uniform(0, 3, n),
            "PTV_D2_gy": eqd2 + rng.uniform(1, 4, n),
            "PTV_D98_gy": eqd2 - rng.uniform(1, 4, n),
            "PTV_Dmean_gy": dmean,
            "PTV_gEUD_gy": geud,
            "PTV_HI": hi,
            "PTV_CI": rng.uniform(0.9, 1.05, n),
            "PTV_BED_gy": bed,
            "PTV_EQD2_gy": eqd2,
            "PTV_dose_skewness": rng.normal(0, 1, n),
            "PTV_dose_kurtosis": rng.normal(0, 1, n),
            "PTV_dose_std_gy": rng.uniform(1, 4, n),
        }
    )
    for oar in _OARS:
        base = rng.uniform(15, 45, n)
        df[f"{oar}_Dmean_gy"] = base
        df[f"{oar}_Dmax_gy"] = base + rng.uniform(5, 25, n)
        df[f"{oar}_gEUD_gy"] = base + rng.uniform(-2, 2, n)
        df[f"{oar}_EQD2mean_gy"] = base * 0.9
        df[f"{oar}_V30Gy_cc"] = rng.uniform(0, 40, n)
        df[f"{oar}_V50Gy_cc"] = rng.uniform(0, 20, n)

    df["age"] = age
    df["hpv_status"] = hpv
    df["t_stage"] = rng.choice(["T1", "T2", "T3", "T4"], size=n)
    df["n_stage"] = rng.choice(["N0", "N1", "N2", "N3"], size=n)
    # Dose-driven endpoints (lower tumour dose -> more recurrence/death).
    p_lr = 1.0 / (1.0 + np.exp(0.6 * (eqd2 - 68)))
    df["locoregional"] = (rng.uniform(size=n) < 0.5 * p_lr).astype(int)
    p_death = 1.0 / (1.0 + np.exp(0.4 * (eqd2 - 69) - 0.03 * (age - 65)))
    df["death"] = (rng.uniform(size=n) < 0.55 * p_death).astype(int)
    df["distant"] = (rng.uniform(size=n) < 0.15).astype(int)
    return df


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    df = make_synthetic_cohort(args.n, args.seed)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False)
    print(
        f"wrote synthetic mirror: {args.out} ({df.shape[0]} rows x {df.shape[1]} cols, "
        f"LR events={int(df['locoregional'].sum())}, death={int(df['death'].sum())})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
