"""
Phase-4 ablations on cohort_features.csv: N-subsampling learning curve and
MCD cohort-consistency (out-of-domain plan flagging).

- N-subsampling: cross-validated AUC vs cohort size for dosiomics-RF and the
  PINN (lambda_phys=0 plain-NN vs lambda_phys=1), to expose the small-sample
  regime where a physics prior should help most.
- MCD-CCS: robust Mahalanobis consistency score on key dose features; flags
  plans that sit outside the cohort's dose-feature domain.

Emits under ``--out-dir``: subsampling_curve.csv, subsampling_curve.png,
ccs_report.json. Reference-planned dose (see docs/EXTVAL_DATA_READINESS.md).

Usage:
    python external_validation/run_phase4_analysis.py \
        --features external_validation/data/cohort_features.csv \
        --out-dir  external_validation/data/benchmark
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
for _p in (_ROOT, _ROOT / "engine"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.ensemble import RandomForestClassifier  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402
from sklearn.model_selection import StratifiedKFold  # noqa: E402

from validation.cohort_consistency import compute_mcd_ccs  # noqa: E402
from validation.extval_benchmark import feature_matrix  # noqa: E402

_CCS_FEATURES = [
    "PTV_EQD2_gy",
    "PTV_gEUD_gy",
    "PTV_HI",
    "Parotids_Dmean_gy",
    "PharynxConstrictor_Dmean_gy",
    "SpinalCord_Dmax_gy",
]


def _cv_auc(make, X: np.ndarray, y: np.ndarray, seed: int, n_splits: int = 3) -> float:
    oof = np.full(len(y), np.nan)
    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    for tr, te in skf.split(X, y):
        if len(np.unique(y[tr])) < 2:
            continue
        est = make()
        est.fit(X[tr], y[tr])
        oof[te] = est.predict_proba(X[te])[:, 1]
    ok = ~np.isnan(oof)
    if len(np.unique(y[ok])) < 2:
        return float("nan")
    return float(roc_auc_score(y[ok], oof[ok]))


def subsampling_curve(
    df: pd.DataFrame,
    endpoint: str,
    ns: tuple[int, ...],
    repeats: int,
    seed: int,
) -> pd.DataFrame:
    from validation.outcome_pinn import OutcomePINN, PINNConfig

    work = df[pd.to_numeric(df[endpoint], errors="coerce").notna()].reset_index(drop=True)
    y_all = pd.to_numeric(work[endpoint], errors="coerce").astype(int).to_numpy()
    Xdf, names = feature_matrix(work, "dosiomics")
    X_all = np.nan_to_num(Xdf.to_numpy(dtype=float), nan=0.0)
    dose_idx = names.index("PTV_EQD2_gy") if "PTV_EQD2_gy" in names else 0

    def rf():
        return RandomForestClassifier(
            n_estimators=200, max_depth=3, min_samples_leaf=5, random_state=seed, n_jobs=1
        )

    def pinn(lam):
        return lambda: OutcomePINN(
            dose_idx=dose_idx,
            config=PINNConfig(
                lambda_phys=lam, lambda_bc=0.5 if lam else 0.0, epochs=150, seed=seed
            ),
        )

    rows = []
    rng = np.random.default_rng(seed)
    for n in ns:
        n = min(n, len(y_all))
        for r in range(repeats):
            idx = rng.choice(len(y_all), size=n, replace=False)
            X, y = X_all[idx], y_all[idx]
            if len(np.unique(y)) < 2:
                continue
            rows.append(
                {
                    "n": n,
                    "repeat": r,
                    "events": int(y.sum()),
                    "auc_rf": _cv_auc(rf, X, y, seed + r),
                    "auc_pinn_plain": _cv_auc(pinn(0.0), X, y, seed + r),
                    "auc_pinn_lq": _cv_auc(pinn(1.0), X, y, seed + r),
                }
            )
    return pd.DataFrame(rows)


def _plot_curve(curve: pd.DataFrame, out_png: Path) -> None:
    agg = curve.groupby("n").mean(numeric_only=True).reset_index()
    fig, ax = plt.subplots(figsize=(7, 5))
    for col, label, style in (
        ("auc_rf", "dosiomics RF", "o-"),
        ("auc_pinn_plain", "PINN (plain, λ=0)", "s--"),
        ("auc_pinn_lq", "PINN (LQ, λ=1)", "^-"),
    ):
        ax.plot(agg["n"], agg[col], style, label=label)
    ax.axhline(0.5, color="grey", lw=0.8, ls=":")
    ax.set_xlabel("cohort size N")
    ax.set_ylabel("cross-validated AUC")
    ax.set_ylim(0.4, 0.85)
    ax.set_title("N-subsampling learning curve (loco-regional; reference-planned dose)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_png, dpi=130)
    plt.close(fig)


def ccs_report(df: pd.DataFrame) -> dict:
    cols = [c for c in _CCS_FEATURES if c in df.columns]
    X = df[cols].apply(pd.to_numeric, errors="coerce").fillna(df[cols].median()).to_numpy(float)
    res = compute_mcd_ccs(X)
    flagged = res.get("flagged_indices", [])
    ids = df.get("patient_id", pd.Series(range(len(df)))).astype(str).to_numpy()
    return {
        "features": cols,
        "n_patients": int(len(df)),
        "n_flagged_out_of_domain": int(len(flagged)),
        "chi2_critical": res.get("chi2_critical"),
        "flagged_patient_ids": [ids[i] for i in flagged],
        "ccs_median": float(np.median(res.get("ccs", [np.nan]))),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features", required=True, type=Path)
    ap.add_argument("--out-dir", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args(argv)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(args.features)

    curve = subsampling_curve(
        df, "locoregional", ns=(40, 60, 80, 100, 121), repeats=3, seed=args.seed
    )
    curve.to_csv(args.out_dir / "subsampling_curve.csv", index=False)
    _plot_curve(curve, args.out_dir / "subsampling_curve.png")
    print("=== N-subsampling (mean CV-AUC by N) ===")
    print(curve.groupby("n").mean(numeric_only=True).round(3).to_string())

    ccs = ccs_report(df)
    (args.out_dir / "ccs_report.json").write_text(json.dumps(ccs, indent=2), encoding="utf-8")
    print("\n=== MCD cohort-consistency ===")
    print(json.dumps(ccs, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
