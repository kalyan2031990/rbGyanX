"""
Four-tier NTCP benchmark (B2) for the internal parotid and external SPARK arms.

Uses rbGyanX's run_four_tier_harness under one leakage-safe protocol:
  T1  classical literature-fixed NTCP (tool params)
  T2  MLE-refit dose-response logistic (on the dose metric)
  T3  clinical-covariate logistic (EPV-gated)
  T4  dosiomics ML (random forest), out-of-fold (grouped) predictions

Adds decision-curve net benefit (DCA) and, for the internal parotid arm, bootstrap
optimism correction on the ML tier. Writes per-arm CSVs to results/.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "engine"))


import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.preprocessing import StandardScaler

from validation.extval_benchmark import net_benefit
from validation.four_tier_harness import run_four_tier_harness


def _default_workspace() -> Path:
    """First rbGyanX_Manuscript_Workspace found walking up from this file."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "rbGyanX_Manuscript_Workspace"
        if candidate.is_dir():
            return candidate
    return Path("rbGyanX_Manuscript_Workspace")


# Workspace root. Was an absolute path into the author's home directory; de-localised when this
# script was committed retrospectively (FINAL_V3.2 consolidation). Set RBGYANX_WORKSPACE to
# point elsewhere. No computation, constant, parameter or threshold was changed.
_WORKSPACE = Path(os.environ.get("RBGYANX_WORKSPACE") or _default_workspace())

RESULTS = Path(_WORKSPACE / "02_Run_Outputs")
RNG = 0


def _oof_rf(X: np.ndarray, y: np.ndarray, groups: np.ndarray, n_splits: int) -> np.ndarray:
    oof = np.full(len(y), np.nan)
    n_splits = min(n_splits, len(np.unique(groups)), int(min(y.sum(), (y == 0).sum())))
    if n_splits < 2:
        return oof
    skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=RNG)
    for tr, te in skf.split(X, y, groups):
        if len(np.unique(y[tr])) < 2:
            continue
        rf = RandomForestClassifier(
            n_estimators=300, max_depth=3, min_samples_leaf=5, random_state=RNG, n_jobs=1
        )
        rf.fit(X[tr], y[tr])
        oof[te] = rf.predict_proba(X[te])[:, 1]
    return oof


def _mle_refit(dose_metric: np.ndarray, y: np.ndarray) -> np.ndarray:
    x = np.nan_to_num(dose_metric, nan=float(np.nanmedian(dose_metric))).reshape(-1, 1)
    xs = StandardScaler().fit_transform(x)
    lr = LogisticRegression(max_iter=500).fit(xs, y)
    return lr.predict_proba(xs)[:, 1]


def run_arm(
    name: str,
    df: pd.DataFrame,
    endpoint: str,
    classical_col: str,
    dose_metric_col: str,
    covariate_cols: list[str],
    dosiomics_cols: list[str],
    groups_col: str | None,
    n_splits: int = 5,
) -> pd.DataFrame:
    work = df[df[endpoint].notna()].reset_index(drop=True)
    y = work[endpoint].astype(int).to_numpy()
    groups = (
        work[groups_col].astype(str).to_numpy()
        if groups_col
        else work["pseudonym"].astype(str).to_numpy()
    )
    p_class = np.clip(work[classical_col].to_numpy(dtype=float), 1e-6, 1 - 1e-6)
    p_mle = _mle_refit(work[dose_metric_col].to_numpy(dtype=float), y)

    Xd = np.nan_to_num(work[dosiomics_cols].to_numpy(dtype=float), nan=0.0)
    p_ml = _oof_rf(Xd, y, groups, n_splits)

    cov = work[covariate_cols].copy()
    res = run_four_tier_harness(
        y_true=y,
        classical_probs=p_class,
        patient_ids=groups,
        clinical_features=cov,
        ml_probs=np.nan_to_num(p_ml, nan=float(y.mean())),
        mle_probs=p_mle,
        n_splits=n_splits,
    )

    rows = []
    tiers = {"T1": res.get("T1"), "T2": res.get("T2"), "T3": res.get("T3"), "T4": res.get("T4")}
    prob_for_dca = {"T1": p_class, "T2": p_mle, "T4": np.nan_to_num(p_ml, nan=float(y.mean()))}
    for tkey, tr in tiers.items():
        if tr is None:
            continue
        nb = net_benefit(y, prob_for_dca[tkey]) if tkey in prob_for_dca else float("nan")
        rows.append(
            {
                "arm": name,
                "endpoint": endpoint,
                "tier": tr.tier,
                "model": tr.model_name,
                "n": int(len(y)),
                "events": int(y.sum()),
                "apparent_auc": round(tr.apparent_auc, 3),
                "cv_auc": round(tr.cv_auc, 3),
                "optimism": round(tr.apparent_auc - tr.cv_auc, 3),
                "brier": round(tr.brier, 3),
                "ece": round(tr.ece, 3),
                "cal_slope": round(tr.calibration_slope, 3),
                "net_benefit": round(nb, 4) if nb == nb else float("nan"),
                "epv": round(tr.epv, 1) if tr.epv is not None else None,
                "refused": tr.refused,
                "note": tr.refusal_reason,
            }
        )
    table = pd.DataFrame(rows)
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"ntcp_benchmark_{name}.csv"
    table.to_csv(out, index=False)
    print(f"\n=== {name}  endpoint={endpoint}  n={len(y)} events={int(y.sum())} ===")
    print(table.to_string(index=False))
    print(f"-> {out}")
    return table


def main() -> None:
    # --- Parotid (internal): xerostomia grade >=2, LKB log-logistic classical ---
    par = pd.read_csv(_WORKSPACE / "02_Run_Outputs" / "PAROTID" / "parotid_cohort.csv")
    run_arm(
        "parotid_xerostomia",
        par,
        endpoint="xerostomia_grade2plus",
        classical_col="NTCP_LL",
        dose_metric_col="Parotid_gEUD_gy",
        covariate_cols=["age", "sex_M", "tobacco_exposure"],
        dosiomics_cols=[
            "Parotid_Dmean_gy",
            "Parotid_gEUD_gy",
            "Parotid_dose_skewness",
            "Parotid_dose_kurtosis",
            "Parotid_dose_std_gy",
        ],
        groups_col=None,
        n_splits=5,
    )

    # --- SPARK (external): GU (viable, 13 ev) + rectal-GI (underpowered, 3 ev) ---
    spark = pd.read_csv(_WORKSPACE / "01_Input_Data" / "SPARK" / "spark_cohort.csv")
    # Classical NTCP proxy: logistic on the OAR mean dose (tool refit) as the fixed model
    # stand-in, since conventional-fractionation LKB params do not transfer to 36.25 Gy/5.
    for ep, oar in [("gu", "Bladder"), ("rectal_gi", "Rectum")]:
        s = spark.copy()
        s[f"{oar}_classical"] = _mle_refit(s[f"{oar}_Dmean_gy"].to_numpy(dtype=float),
                                           s[ep].astype(int).to_numpy())
        run_arm(
            f"spark_{ep}",
            s,
            endpoint=ep,
            classical_col=f"{oar}_classical",
            dose_metric_col=f"{oar}_gEUD_gy",
            covariate_cols=[f"{oar}_Dmean_gy"],  # no clinical covariates in SPARK derived
            dosiomics_cols=[f"{oar}_Dmean_gy", f"{oar}_gEUD_gy", "PTV_Dmean_gy"],
            groups_col="centre",
            n_splits=4,
        )


if __name__ == "__main__":
    main()


