"""XAI (SHAP) for the v2 models — the v1 SHAP ran on the synthetic dosiomics and is superseded.

Two deliverables per cohort:

1. **Global + per-patient SHAP** for the v2 best model, fitted on the full cohort. SHAP explains the
   fitted model, not the cross-validated performance; it is in-sample and associational by construction
   and is labelled as such.
2. **Fold selection frequency** for TCIA_HN — how often each texture feature survived the nested
   univariate filter across the 25 training folds. A feature that is "important" in SHAP but selected in
   only a few folds is unstable and must not be presented as a biomarker.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from v2_pinn import dosio_alias_map, feature_cols, select_texture_in_fold, standardise


def fold_selection_frequency(df: pd.DataFrame, y: np.ndarray, seed: int,
                             folds: int = 5, repeats: int = 5) -> pd.DataFrame:
    from sklearn.model_selection import StratifiedKFold
    all_cols = feature_cols(df, True)
    counts: dict[str, int] = {}
    n_part = 0
    for rep in range(repeats):
        skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=seed + 100 * rep)
        for tr, _ in skf.split(df, y):
            sel = select_texture_in_fold(df.iloc[tr].reset_index(drop=True), y[tr], all_cols)
            n_part += 1
            for c in sel:
                if c.startswith("dosio_"):
                    counts[c] = counts.get(c, 0) + 1
    rows = [{"feature": k, "folds_selected": v, "folds_total": n_part,
             "selection_frequency": v / n_part} for k, v in counts.items()]
    return pd.DataFrame(rows).sort_values("folds_selected", ascending=False)


def shap_for(model, X: np.ndarray, cols: list[str], kind: str):
    import shap
    if kind == "tree":
        ex = shap.TreeExplainer(model)
        sv = ex.shap_values(X)
        if isinstance(sv, list):
            sv = sv[1]
        elif getattr(sv, "ndim", 2) == 3:
            sv = sv[:, :, 1]
    else:
        ex = shap.LinearExplainer(model, X)
        sv = ex.shap_values(X)
    sv = np.asarray(sv)
    glob = pd.DataFrame({"feature": cols,
                         "mean_abs_shap": np.abs(sv).mean(axis=0),
                         "mean_shap": sv.mean(axis=0)}).sort_values("mean_abs_shap", ascending=False)
    per = pd.DataFrame(sv, columns=[f"shap__{c}" for c in cols])
    return glob, per


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True, type=Path, help="patient_features_ALL.csv dir")
    ap.add_argument("--pinn-frame", required=True, type=Path, help="V2_PINN_input_features.csv")
    ap.add_argument("--texture", required=True, type=Path, help="real_dosiomics_*_wide.csv")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    alias = dosio_alias_map(pd.read_csv(a.texture, low_memory=False))
    pd.DataFrame([{"alias": k, "texture_feature": v} for k, v in alias.items()]).to_csv(
        a.out / "V2_XAI_dosiomics_alias_map.csv", index=False)

    def named(s):
        return s.map(lambda c: alias.get(c, c))

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression

    manifest = {"note": "SHAP is in-sample and associational; it explains the fitted model, "
                        "not the cross-validated performance.", "models": []}

    # ---- TCIA_HN: v2 best = random forest on dose + clinical + nested-selected texture ------------
    hn = pd.read_csv(a.pinn_frame, low_memory=False)
    y = hn["tcp_outcome"].astype(int).values          # 1 = loco-regionally controlled
    body = hn.drop(columns=["pseudonym"])
    freq = fold_selection_frequency(body, y, a.seed)
    freq.insert(1, "texture_feature", named(freq["feature"]))
    freq.to_csv(a.out / "V2_XAI_TCIA_HN_fold_selection_frequency.csv", index=False)

    # explain the model built on the features that survive in the MAJORITY of folds - anything less
    # stable than that should not be interpreted at all
    stable = freq.loc[freq.selection_frequency >= 0.5, "feature"].tolist()
    cols = [c for c in feature_cols(body, False)] + stable
    A, _ = standardise(body, body, cols)
    rf = RandomForestClassifier(n_estimators=600, min_samples_leaf=5,
                                class_weight="balanced_subsample", random_state=a.seed, n_jobs=-1)
    rf.fit(A, y)
    g, p = shap_for(rf, A, cols, "tree")
    g.insert(1, "readable_name", named(g["feature"]))
    g.to_csv(a.out / "V2_XAI_shap_global_TCIA_HN_locoregional.csv", index=False)
    pd.concat([hn[["pseudonym"]], pd.Series(y, name="outcome_controlled"), p], axis=1).to_csv(
        a.out / "V2_XAI_shap_per_patient_TCIA_HN_locoregional.csv", index=False)
    manifest["models"].append({
        "cohort": "TCIA_HN", "outcome": "locoregional_control", "n": int(len(hn)),
        "events_controlled": int(y.sum()), "model": "random_forest",
        "features": cols, "n_features": len(cols),
        "stable_texture_features": [alias.get(c, c) for c in stable],
        "explainer": "TreeExplainer",
        "caveat": "texture features shown are those selected in >=50% of the 25 training folds",
    })

    # ---- Parotid: v2 best = elastic-net logistic on dose + clinical ------------------------------
    master = pd.read_csv(a.features / "patient_features_ALL.csv", low_memory=False)
    pg = master[(master.cohort == "Parotid") & (master.outcome_available == 1)].copy()
    ycol = "outcome_xerostomia_g2plus"
    pcols = [c for c in ("Parotid_unspecified__Dmean_gy", "Parotid_unspecified__gEUD_gy",
                         "clin_age", "clin_sex_M", "clin_tobacco_exposure")
             if c in pg.columns]
    if not pcols:                     # fall back to whatever dose/clinical columns this table carries
        pcols = [c for c in pg.columns
                 if ("Parotid" in c and ("gEUD" in c or "Dmean" in c)) or c.startswith("clin_")]
    pg = pg[np.isfinite(pd.to_numeric(pg[ycol], errors="coerce"))]
    if len(pg) and pcols:
        yp = pd.to_numeric(pg[ycol], errors="coerce").astype(int).values
        B, _ = standardise(pg, pg, pcols)
        en = LogisticRegression(max_iter=5000, l1_ratio=0.5, C=0.5, solver="saga",
                                penalty="elasticnet", class_weight="balanced")
        en.fit(B, yp)
        g2, p2 = shap_for(en, B, pcols, "linear")
        g2.to_csv(a.out / "V2_XAI_shap_global_Parotid_xerostomia_g2plus.csv", index=False)
        pd.concat([pg[["pseudonym"]].reset_index(drop=True),
                   pd.Series(yp, name="outcome_xerostomia_g2plus"), p2], axis=1).to_csv(
            a.out / "V2_XAI_shap_per_patient_Parotid_xerostomia_g2plus.csv", index=False)
        manifest["models"].append({
            "cohort": "Parotid", "outcome": "xerostomia_g2plus", "n": int(len(pg)),
            "events": int(yp.sum()), "model": "elasticnet_logistic",
            "features": pcols, "n_features": len(pcols), "explainer": "LinearExplainer",
        })
    else:
        manifest["models"].append({"cohort": "Parotid", "status": "NOT EXECUTED",
                                   "reason": "no usable dose/clinical columns in the feature table"})

    (a.out / "V2_XAI_manifest.json").write_text(json.dumps(manifest, indent=2, default=str),
                                                encoding="utf-8")
    for m in manifest["models"]:
        print("  XAI", m.get("cohort"), m.get("status", "EXECUTED"), m.get("n_features", ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
