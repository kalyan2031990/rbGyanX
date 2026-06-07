#!/usr/bin/env python3
import argparse, os, sys, math, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# optional imports
try:
    import xgboost as xgb
    HAS_XGB = True
except Exception:
    HAS_XGB = False

from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss

import shap

# Import refactored SHAP utilities
from utils.shap_utils import (
    safe_shap_values,
    to_matrix,
    plot_summary_bar,
    plot_beeswarm,
    generate_shap_caption
)

META_COLS = ["PatientID","Organ","Observed_Toxicity","Set"]
DVH_COLS = ["mean_dose","max_dose","geud","v20","v25","v30","d50","d0.1cc","d1cc"]
CLINICAL_CANDIDATES = ["Technique","DosePerFraction","TotalDose","TotalTreatmentWeeks","FollowUpMonths"]

def pick_columns(df, only_dvh=False):
    cols = DVH_COLS.copy()
    if not only_dvh:
        for c in CLINICAL_CANDIDATES:
            if c in df.columns:
                cols.append(c)
    return [c for c in cols if c in df.columns]

def split_by_set(df, eval_split="Test"):
    if "Set" in df.columns:
        train_mask = df["Set"].astype(str).str.lower().isin(["train","val"])
        eval_mask  = df["Set"].astype(str).str.lower()==eval_split.lower()
        return df[train_mask].copy(), df[eval_mask].copy()
    # fallback: 70/30 random split
    rng = np.random.default_rng(42)
    idx = np.arange(len(df))
    rng.shuffle(idx)
    cut = int(0.7*len(idx))
    tr, te = idx[:cut], idx[cut:]
    return df.iloc[tr].copy(), df.iloc[te].copy()

def one_hot(df, cols):
    # one-hot Technique if present
    if "Technique" in cols and "Technique" in df.columns:
        oh = pd.get_dummies(df["Technique"].astype(str), prefix="Tech", drop_first=True)
        df = pd.concat([df.drop(columns=["Technique"]), oh], axis=1)
        cols = [c for c in cols if c!="Technique"] + list(oh.columns)
    return df, cols

def ensure_numeric(df, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def run_xgb(X_train, y_train):
    if not HAS_XGB:
        return None
    model = xgb.XGBClassifier(
        n_estimators=200, max_depth=3, learning_rate=0.05,
        subsample=0.9, colsample_bytree=0.8, reg_lambda=1.0,
        random_state=42, eval_metric="logloss", n_jobs=0
    )
    model.fit(X_train, y_train)
    return model

def run_ann(X_train, y_train):
    # scale inside pipeline
    clf = Pipeline([
        ("scaler", StandardScaler()),
        ("mlp", MLPClassifier(hidden_layer_sizes=(32,16), alpha=1e-4,
                              max_iter=1000, random_state=42,
                              early_stopping=True, n_iter_no_change=20, validation_fraction=0.15))
    ])
    clf.fit(X_train, y_train)
    return clf

def eval_and_shap(model, model_name, organ, X_train, y_train, X_eval, y_eval, outdir):
    # metrics
    if hasattr(model, "predict_proba"):
        p = model.predict_proba(X_eval)[:,1]
    else:
        p = model.predict(X_eval)
        if p.ndim==1:
            p = np.clip(p,0,1)
    auc = roc_auc_score(y_eval, p) if len(np.unique(y_eval))>1 else float("nan")
    try:
        brier = brier_score_loss(y_eval, p)
    except Exception:
        brier = float("nan")

    # SHAP
    explainer, sv = safe_shap_values(model, X_train, X_eval)
    sv = to_matrix(sv)

    # plots
    organ_dir = os.path.join(outdir, organ.replace(" ","_"), model_name)
    os.makedirs(organ_dir, exist_ok=True)

    bar_png  = os.path.join(organ_dir, f"shap_bar_{model_name}_{organ}.png")
    swarm_png= os.path.join(organ_dir, f"shap_beeswarm_{model_name}_{organ}.png")
    plot_summary_bar(sv, X_eval, bar_png)
    plot_beeswarm(sv, X_eval, swarm_png)

    # caption
    capt = generate_shap_caption(sv, X_eval.columns, model_name, organ)
    with open(os.path.join(organ_dir, "caption.txt"), "w", encoding="utf-8") as f:
        f.write(capt + f"\nAUC={auc:.3f}; Brier={brier:.3f}\n")

    # save metrics
    with open(os.path.join(organ_dir, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump({"AUC": auc, "Brier": brier, "n_eval": int(X_eval.shape[0])}, f, indent=2)

    print(f"  [OK] {organ} [{model_name}]  AUC={auc:.3f}  Brier={brier:.3f}  -> {organ_dir}")

def main():
    ap = argparse.ArgumentParser(description="Clean SHAP runner")
    ap.add_argument("--features_csv", required=True)
    ap.add_argument("--outdir", default="shap_outputs")
    ap.add_argument("--organ", default=None, help="Parotid / Larynx / SpinalCord (optional)")
    ap.add_argument("--split", default="Test", help="Eval split (default: Test). Train = Train+Val")
    ap.add_argument("--models", default="both", choices=["xgb","ann","both"])
    ap.add_argument("--only_dvh", action="store_true", help="Restrict to DVH features only")
    args = ap.parse_args()

    df = pd.read_csv(args.features_csv)
    if args.organ:
        df = df[df["Organ"].astype(str).str.lower()==args.organ.lower()].copy()
        if df.empty:
            print(f"No rows found for organ '{args.organ}'."); sys.exit(1)

    use_cols = pick_columns(df, only_dvh=args.only_dvh)
    df = ensure_numeric(df, use_cols)
    df, use_cols = one_hot(df, use_cols)

    # drop rows with missing y or features
    df = df.dropna(subset=["Observed_Toxicity"] + use_cols).copy()
    train_df, eval_df = split_by_set(df, eval_split=args.split)
    if train_df.empty or eval_df.empty:
        print("Empty train/eval after split; check your Set column."); sys.exit(1)

    X_train = train_df[use_cols].copy()
    y_train = train_df["Observed_Toxicity"].astype(int).to_numpy()
    X_eval  = eval_df[use_cols].copy()
    y_eval  = eval_df["Observed_Toxicity"].astype(int).to_numpy()

    os.makedirs(args.outdir, exist_ok=True)
    # Decide organ name for folder/captions
    organ_name = args.organ if args.organ else "AllOrgans"

    if args.models in ("xgb","both") and HAS_XGB:
        model = run_xgb(X_train, y_train)
        eval_and_shap(model, "XGBoost", organ_name, X_train, y_train, X_eval, y_eval, args.outdir)
    elif args.models in ("xgb","both") and not HAS_XGB:
        print("! XGBoost not installed; skipping XGB.")

    if args.models in ("ann","both"):
        model = run_ann(X_train, y_train)
        eval_and_shap(model, "ANN", organ_name, X_train, y_train, X_eval, y_eval, args.outdir)

if __name__ == "__main__":
    main()
