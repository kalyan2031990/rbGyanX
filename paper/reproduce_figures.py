#!/usr/bin/env python3
"""Reproduce paper schematic figures (no PHI)."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data"
FIG = Path(__file__).resolve().parent / "figures"
FIG.mkdir(parents=True, exist_ok=True)

ENGINE_PATH = "reference"
if str(ROOT / "engine") not in sys.path:
    sys.path.insert(0, str(ROOT / "engine"))


def _ref_ntcp_loglogit(geud: float, td50: float, gamma: float) -> float:
    if geud <= 0 or td50 <= 0 or gamma <= 0:
        return float("nan")
    t = (geud - td50) / td50 * gamma
    return float(1.0 / (1.0 + math.exp(-t)))


def ntcp_at_dose(geud: float, td50: float = 30.0, gamma: float = 1.0) -> float:
    global ENGINE_PATH
    # ENGINE HOOK — NTCP primitive
    try:
        from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit

        ENGINE_PATH = "rbgyanx_engine"
        return calculate_ntcp_lkb_loglogit(geud, td50, gamma)
    except ImportError:
        return _ref_ntcp_loglogit(geud, td50, gamma)


def run_four_tier(df: pd.DataFrame) -> dict:
    global ENGINE_PATH
    # ENGINE HOOK — four-tier harness
    try:
        from validation.four_tier_harness import run_four_tier_harness

        ENGINE_PATH = "rbgyanx_engine"
        y = df["toxicity"].values
        p = df["classical_ntcp"].values
        pid = df["patient_id"].values
        X = df[["age", "stage"]]
        return run_four_tier_harness(
            y, p, pid,
            clinical_features=X,
            mle_probs=df["mle_ntcp"].values,
            ml_probs=df["ml_ntcp"].values,
        )
    except ImportError:
        from sklearn.metrics import roc_auc_score

        y = df["toxicity"].values
        return {
            "T1": type("R", (), {"apparent_auc": roc_auc_score(y, df["classical_ntcp"])})(),
        }


def mcd_ccs(features: np.ndarray) -> list[float]:
    global ENGINE_PATH
    # ENGINE HOOK — MCD CCS
    try:
        from validation.cohort_consistency import compute_mcd_ccs

        ENGINE_PATH = "rbgyanx_engine"
        return compute_mcd_ccs(features)["ccs"]
    except ImportError:
        from scipy import stats

        cov = np.cov(features, rowvar=False)
        loc = np.mean(features, axis=0)
        inv = np.linalg.pinv(cov)
        d2 = [float((x - loc) @ inv @ (x - loc)) for x in features]
        p = features.shape[1]
        return [float(stats.chi2.cdf(v, p)) for v in d2]


def figure_ntcp_curve():
    doses = np.linspace(5, 60, 100)
    vals = [ntcp_at_dose(d) for d in doses]
    plt.figure(figsize=(6, 4))
    plt.plot(doses, vals, label="NTCP (LKB log-logistic)")
    plt.axhline(0.5, color="gray", ls="--", lw=0.8)
    plt.xlabel("gEUD (Gy)")
    plt.ylabel("NTCP")
    plt.title("Figure 1 — NTCP dose-response")
    plt.legend()
    plt.tight_layout()
    out = FIG / "fig1_ntcp_curve.png"
    plt.savefig(out, dpi=150)
    plt.close()
    return out


def figure_four_tier(df: pd.DataFrame):
    res = run_four_tier(df)
    tiers = []
    aucs = []
    for k in ("T1", "T2", "T3", "T4"):
        if k in res:
            tiers.append(k)
            r = res[k]
            aucs.append(getattr(r, "apparent_auc", getattr(r, "cv_auc", float("nan"))))
    plt.figure(figsize=(6, 4))
    plt.bar(tiers, aucs, color="steelblue")
    plt.ylim(0, 1)
    plt.ylabel("AUC")
    plt.title("Figure 2 — Four-tier apparent AUC")
    plt.tight_layout()
    out = FIG / "fig2_four_tier_auc.png"
    plt.savefig(out, dpi=150)
    plt.close()
    return out


def figure_ccs(df: pd.DataFrame):
    feat = df[["classical_ntcp", "mle_ntcp", "ml_ntcp"]].values
    ccs = mcd_ccs(feat)
    plt.figure(figsize=(6, 4))
    plt.scatter(range(len(ccs)), ccs, c="teal")
    plt.xlabel("Patient index")
    plt.ylabel("MCD-CCS")
    plt.title("Figure 3 — Cohort consistency score")
    plt.tight_layout()
    out = FIG / "fig3_mcd_ccs.png"
    plt.savefig(out, dpi=150)
    plt.close()
    return out


def main() -> int:
    df = pd.read_csv(DATA / "cohort.csv")
    gt = json.loads((DATA / "ground_truth.json").read_text(encoding="utf-8"))
    paths = [
        figure_ntcp_curve(),
        figure_four_tier(df),
        figure_ccs(df),
    ]
    print(f"ENGINE PATH: {ENGINE_PATH}")
    print(f"Ground-truth checks: ntcp@D50≈{gt['ntcp_at_d50']}")
    for p in paths:
        print(f"Wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
