"""Fair comparators for the v2 hybrid PINN.

Runs plain logistic regression / elastic net / random forest through the EXACT same protocol as the
PINN (5-fold x 5-repeat stratified CV, texture selected inside each training fold, train-fold-only
standardisation). Without this the PINN AUC cannot be interpreted: a physics-informed network is only
worth reporting if it is not beaten by a linear model on the same inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from v2_pinn import auc, auc_ci, feature_cols, select_texture_in_fold, standardise


def run(df: pd.DataFrame, use_texture: bool, seed: int, folds: int = 5, repeats: int = 5) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold

    y = df["tcp_outcome"].astype(int).values
    all_cols = feature_cols(df, use_texture)
    models = {
        "logistic": lambda: LogisticRegression(max_iter=2000, class_weight="balanced"),
        "elasticnet": lambda: LogisticRegression(max_iter=5000, penalty="elasticnet", solver="saga",
                                                 l1_ratio=0.5, C=0.5, class_weight="balanced"),
        "random_forest": lambda: RandomForestClassifier(n_estimators=400, min_samples_leaf=5,
                                                        class_weight="balanced_subsample",
                                                        random_state=seed, n_jobs=-1),
    }
    acc = {m: np.zeros(len(df)) for m in models}
    cnt = np.zeros(len(df))
    for rep in range(repeats):
        skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed + 100 * rep)
        for tr, te in skf.split(df, y):
            tr_df = df.iloc[tr].reset_index(drop=True)
            te_df = df.iloc[te].reset_index(drop=True)
            cols = select_texture_in_fold(tr_df, y[tr], all_cols) if use_texture else all_cols
            A, B = standardise(tr_df, te_df, cols)
            for name, mk in models.items():
                m = mk()
                m.fit(A, y[tr])
                acc[name][te] += m.predict_proba(B)[:, 1]
            cnt[te] += 1
    out = {}
    for name in models:
        p = acc[name] / np.maximum(cnt, 1)
        out[name] = {
            "cv_AUC": auc(y, p),
            "cv_AUC_bootstrap95": auc_ci(y, p, seed),
            "cv_MAE": float(np.mean(np.abs(p - y))),
            "cv_Brier": float(np.mean((p - y) ** 2)),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--frame", required=True, type=Path, help="V2_PINN_input_features.csv")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(a.frame, low_memory=False)
    base_cols = [c for c in df.columns if not c.startswith("dosio_")]
    rows = []
    for label, d, tex in (("dose+clinical", df[base_cols], False),
                          ("dose+clinical+texture", df, True)):
        for name, r in run(d.drop(columns=["pseudonym"]), tex, a.seed).items():
            lo, hi = r["cv_AUC_bootstrap95"]
            rows.append({"feature_set": label, "model": name, **r,
                         "auc_lo": lo, "auc_hi": hi})
            print(f"  {label:24s} {name:14s} cvAUC={r['cv_AUC']:.3f} [{lo:.3f}-{hi:.3f}] "
                  f"MAE={r['cv_MAE']:.3f}")
    res = pd.DataFrame(rows)
    res.drop(columns=["cv_AUC_bootstrap95"]).to_csv(a.out / "V2_PINN_COMPARATORS.csv", index=False)
    (a.out / "V2_PINN_COMPARATORS.json").write_text(json.dumps(rows, indent=2, default=str),
                                                    encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
