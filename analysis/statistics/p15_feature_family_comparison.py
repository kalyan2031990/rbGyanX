"""Phase 15 - clinical vs radiobiology vs dosiomics vs CT radiomics, and their combinations.

Eight pre-specified arms on the outcome-linked TCIA multimodal cohort. Every arm goes through the
identical protocol: 5-fold x 5-repeat stratified CV, standardisation and feature selection fitted
**inside each training fold only**, patient bootstrap CIs.

The selection-inside-the-fold rule is what makes the comparison admissible. A high-dimensional
radiomics arm will always look superior if its features are chosen on the whole cohort first; that is
the single most common way a radiomics paper overstates its result, and it is structurally prevented
here rather than merely disclaimed.

Arms whose feature family is unavailable for this cohort are reported as NOT AVAILABLE with a reason,
never silently dropped or back-filled.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from v2_pinn import auc, auc_ci, standardise

TOP_K = 12          # per high-dimensional family, selected inside each training fold


def select_in_fold(tr: pd.DataFrame, y: np.ndarray, cols: list[str], k: int) -> list[str]:
    from scipy.stats import spearmanr
    if len(cols) <= k:
        return cols
    scored = []
    for c in cols:
        v = pd.to_numeric(tr[c], errors="coerce").values.astype(float)
        if not np.isfinite(v).any() or np.nanstd(v) < 1e-12:
            continue
        v = np.where(np.isfinite(v), v, np.nanmedian(v))
        r = spearmanr(v, y).statistic
        scored.append((abs(r) if np.isfinite(r) else 0.0, c))
    scored.sort(reverse=True)
    return [c for _, c in scored[:k]]


def evaluate(df: pd.DataFrame, y: np.ndarray, fixed: list[str], selectable: list[str],
             seed: int = 0, folds: int = 5, repeats: int = 5) -> dict:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    models = {
        "logistic": lambda: LogisticRegression(max_iter=3000, class_weight="balanced"),
        "random_forest": lambda: RandomForestClassifier(
            n_estimators=400, min_samples_leaf=5, class_weight="balanced_subsample",
            random_state=seed, n_jobs=-1),
    }
    acc = {m: np.zeros(len(df)) for m in models}
    cnt = np.zeros(len(df))
    ksel = []
    for rep in range(repeats):
        for tr, te in StratifiedKFold(folds, shuffle=True,
                                      random_state=seed + 100 * rep).split(df, y):
            trd = df.iloc[tr].reset_index(drop=True)
            ted = df.iloc[te].reset_index(drop=True)
            cols = fixed + (select_in_fold(trd, y[tr], selectable, TOP_K) if selectable else [])
            cols = [c for c in cols if c in df.columns]
            if not cols:
                continue
            ksel.append(len(cols))
            A, B = standardise(trd, ted, cols)
            for name, mk in models.items():
                acc[name][te] += mk().fit(A, y[tr]).predict_proba(B)[:, 1]
            cnt[te] += 1
    out = {}
    for name in models:
        if cnt.sum() == 0:
            continue
        p = acc[name] / np.maximum(cnt, 1)
        lo, hi = auc_ci(y, p, seed)
        # sensitivity/specificity at the prevalence-matched threshold
        thr = float(np.quantile(p, 1 - y.mean()))
        pred = (p >= thr).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        # calibration slope on the logit scale
        eps = 1e-6
        lp = np.log(np.clip(p, eps, 1 - eps) / (1 - np.clip(p, eps, 1 - eps)))
        try:
            from sklearn.linear_model import LogisticRegression as LR
            cal = LR(max_iter=1000).fit(lp.reshape(-1, 1), y)
            slope, icpt = float(cal.coef_[0][0]), float(cal.intercept_[0])
        except Exception:
            slope = icpt = float("nan")
        # PR-AUC (average precision)
        order = np.argsort(-p)
        ys = y[order]
        tpc = np.cumsum(ys)
        prec = tpc / (np.arange(len(ys)) + 1)
        rec = tpc / max(ys.sum(), 1)
        ap = float(np.sum(np.diff(np.concatenate([[0], rec])) * prec))
        out[name] = {"cv_AUC": auc(y, p), "auc_lo95": lo, "auc_hi95": hi,
                     "PR_AUC": ap, "Brier": float(np.mean((p - y) ** 2)),
                     "cal_slope": slope, "cal_intercept": icpt,
                     "sensitivity": tp / max(tp + fn, 1), "specificity": tn / max(tn + fp, 1),
                     "features_per_fold": int(np.median(ksel)) if ksel else 0}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    W = a.workspace
    V2 = W / "03_Statistical_Analysis" / "results_v2_real_dosiomics"
    V3 = W / "03_Statistical_Analysis" / "results_v3_multimodal"

    frame = pd.read_csv(V2 / "pinn_v2" / "V2_PINN_input_features.csv", low_memory=False)
    y = (1 - pd.to_numeric(frame["tcp_outcome"], errors="coerce")).astype(int).values  # FAILURE = 1

    clin = [c for c in ("clin_age", "clin_sex_M", "clin_stage", "clin_hpv_pos")
            if c in frame.columns]
    radbio = [c for c in ("EQD2_gy", "BED_gy", "TCP_Poisson", "TCP_gEUD") if c in frame.columns]
    dosevol = [c for c in ("Dmean_gy", "D95_gy") if c in frame.columns]
    dosio = [c for c in frame.columns if c.startswith("dosio_")]

    # CT radiomics, mapped from TCIA PatientID to pseudonym
    rad_cols: list[str] = []
    radf = V3 / "radiomics" / "radiomics_features_qc.csv"
    pm = W / "09_Audit_Trail" / "_pseudonym_maps" / "TCIA_HN_pseudonym_map.csv"
    rad_note = ""
    if radf.is_file() and pm.is_file():
        r = pd.read_csv(radf, low_memory=False)
        m = pd.read_csv(pm)[["pseudonym", "raw_patient_key"]]
        r = r.merge(m, left_on="patient_id", right_on="raw_patient_key", how="inner")
        rad_cols = [c for c in r.columns if c.startswith("ctrx_")]
        frame = frame.merge(r[["pseudonym", *rad_cols]], on="pseudonym", how="left")
        have = frame[rad_cols].notna().any(axis=1) if rad_cols else pd.Series(False,
                                                                             index=frame.index)
        rad_note = (f"{int(have.sum())} of {len(frame)} outcome-linked patients also carry CT "
                    f"radiomics ({len(rad_cols)} QC-passed features)")
    else:
        rad_note = "CT radiomics not available at run time"

    arms = [
        ("A. Clinical only", clin, []),
        ("B. Classical radiobiology only", radbio, []),
        ("C. Dose/DVH + dosiomics", dosevol, dosio),
        ("D. CT radiomics only", [], rad_cols),
        ("E. Clinical + radiobiology", clin + radbio, []),
        ("F. Clinical + dosiomics", clin + dosevol, dosio),
        ("G. Clinical + CT radiomics", clin, rad_cols),
        ("H. Clinical + CT radiomics + dosiomics", clin + dosevol, rad_cols + dosio),
    ]

    rows = []
    for name, fixed, sel in arms:
        if not fixed and not sel:
            rows.append({"arm": name, "model": "-", "status": "NOT AVAILABLE",
                         "reason": "no feature of this family exists for this cohort"})
            continue
        sub = frame.copy()
        if sel and sel == rad_cols:
            sub = sub[sub[rad_cols].notna().any(axis=1)].reset_index(drop=True)
        elif rad_cols and any(c in sel for c in rad_cols):
            sub = sub[sub[rad_cols].notna().any(axis=1)].reset_index(drop=True)
        yy = (1 - pd.to_numeric(sub["tcp_outcome"], errors="coerce")).astype(int).values
        if len(sub) < 40 or len(np.unique(yy)) < 2:
            rows.append({"arm": name, "model": "-", "status": "NOT AVAILABLE",
                         "reason": f"only {len(sub)} patients with this family and an outcome"})
            continue
        res = evaluate(sub, yy, fixed, sel, a.seed)
        for model, r in res.items():
            rows.append({"arm": name, "model": model, "status": "COMPUTED",
                         "n": int(len(sub)), "events": int(yy.sum()), **r})
            print(f"  {name:42s} {model:14s} n={len(sub):3d} AUC={r['cv_AUC']:.3f} "
                  f"[{r['auc_lo95']:.3f}-{r['auc_hi95']:.3f}] PR={r['PR_AUC']:.3f} "
                  f"Brier={r['Brier']:.3f} k={r['features_per_fold']}")

    out = pd.DataFrame(rows)
    out.to_csv(a.out / "P15_feature_family_comparison.csv", index=False)
    (a.out / "P15_manifest.json").write_text(json.dumps({
        "protocol": "5-fold x 5-repeat stratified CV; standardisation and feature selection inside "
                    "each training fold; patient bootstrap CIs (2000)",
        "top_k_per_high_dim_family": TOP_K, "seed": a.seed,
        "endpoint": "loco-regional failure (1 = failure)",
        "radiomics_note": rad_note,
        "n_clinical": len(clin), "n_radiobiology": len(radbio), "n_dose": len(dosevol),
        "n_dosiomics": len(dosio), "n_ct_radiomics": len(rad_cols),
    }, indent=2), encoding="utf-8")
    print("\n", rad_note)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
