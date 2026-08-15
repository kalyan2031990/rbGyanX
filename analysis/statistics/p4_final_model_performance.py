"""Phase 4 - consolidate every executed model into one performance table, and audit its leakage status.

One row per (paradigm, cohort, endpoint, model, feature set). The `leakage_status` and
`quotable` columns are the point: several rows exist only to document a superseded or
selection-biased estimate, and those must never reach a manuscript.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    W, O = a.workspace, a.out
    O.mkdir(parents=True, exist_ok=True)
    VR = W / "08_Validation_Reports"
    V3 = W / "03_Statistical_Analysis" / "results_v3_multimodal"
    rows = []

    def add(**kw):
        rows.append(kw)

    # ---- classical radiobiology discrimination, from the univariable statistics ------------
    st = pd.read_csv(W / "05_STATISTICS" / "statistical_results.csv")
    for var, coh, ep, label in (
            ("NTCP__Parotid_unspecified__LKB_loglogit", "Parotid", "xerostomia G>=2",
             "LKB log-logistic NTCP"),
            ("NTCP__Parotid_unspecified__RS", "Parotid", "xerostomia G>=2",
             "Relative seriality NTCP")):
        x = st[st.variable == var]
        if len(x):
            add(paradigm="L1 Classical radiobiology", cohort=coh, endpoint=ep, model=label,
                feature_set="gEUD (a=1)", n=int(x.n.iat[0]), events=34,
                AUC=float(x.AUC.iat[0]), AUC_lo95=float(x.AUC_lo95.iat[0]),
                AUC_hi95=float(x.AUC_hi95.iat[0]), Brier=np.nan,
                validation="univariable, bootstrap CI (2000)",
                leakage_status="none - no fitting on these data",
                quotable=True,
                note="calibration concordant (0.59 predicted vs 0.63 observed); discrimination at chance")

    # ---- ML and logistic ---------------------------------------------------------------------
    ml = pd.read_csv(VR / "FINAL_ML_PERFORMANCE_SUMMARY.csv")
    for _, r in ml.iterrows():
        ver = str(r.get("analysis_version"))
        if ver == "v1":
            continue
        fs = str(r.get("feature_set", ""))
        nested = ver == "v2-nested"
        biased = ("texture" in fs.lower()) and not nested
        model = str(r.get("model", ""))
        add(paradigm="L2 Multivariable logistic" if "logistic" in model.lower() and
            "elastic" not in model.lower() else "L3 Machine learning",
            cohort=r.get("cohort"), endpoint=r.get("outcome"), model=model, feature_set=fs,
            n=r.get("n"), events=r.get("events"), AUC=r.get("AUC"),
            AUC_lo95=r.get("AUC_lo95"), AUC_hi95=r.get("AUC_hi95"), Brier=r.get("Brier"),
            validation="5-fold x 5-repeat CV" + (", selection inside folds" if nested else ""),
            leakage_status="none - selection inside training folds" if nested else
            ("FEATURE-SELECTION LEAKAGE - selected on the whole cohort" if biased else
             "none - no feature selection"),
            quotable=bool(not biased),
            note=str(r.get("notes", "") or ""))

    # ---- PINN and its comparators ---------------------------------------------------------------
    pn = pd.read_csv(VR / "FINAL_PINN_SUMMARY.csv")
    for _, r in pn.iterrows():
        variant = str(r.variant)
        is_cmp = variant.startswith("COMPARATOR")
        shipped = variant.startswith("A.")
        add(paradigm="L3 Machine learning (comparator)" if is_cmp else "L5 PINN",
            cohort=r.cohort, endpoint=r.outcome, model=variant,
            feature_set=str(r.architecture), n=r.n, events=20, AUC=r.AUC,
            AUC_lo95=r.AUC_lo95, AUC_hi95=r.AUC_hi95, Brier=r.Brier,
            validation="5-fold x 5-repeat CV, selection inside folds, 3-seed ensemble",
            leakage_status="none - selection inside training folds",
            quotable=bool(not shipped),
            note="superseded v1 architecture, 1 distinct prediction" if shipped else
                 f"MAE {r.get('MAE')}, base-rate MAE {r.get('base_rate_MAE')}")

    # ---- Bayesian / MLE dose-response -----------------------------------------------------------
    bs = pd.read_csv(VR / "FINAL_BAYESIAN_NTCP_SUMMARY.csv")
    for _, r in bs.iterrows():
        valid = bool(r.is_valid_ntcp_endpoint)
        add(paradigm="L6 Bayesian (bootstrap MLE)", cohort=r.cohort,
            endpoint=f"{r.organ} / {r.endpoint}", model="LKB bootstrap MLE",
            feature_set="gEUD", n=r.n, events=r.events, AUC=np.nan, AUC_lo95=np.nan,
            AUC_hi95=np.nan, Brier=np.nan,
            validation="2000-resample bootstrap; percentile CI (NOT MCMC, NOT a credible interval)",
            leakage_status="n/a - dose-response fit, not a predictive model",
            quotable=valid,
            note=f"TD50 {r.TD50_gy:.1f} ({r['TD50_CI2.5']:.1f}-{r['TD50_CI97.5']:.1f}) Gy; "
                 f"{r.verdict}")

    # ---- CCS -------------------------------------------------------------------------------------
    cf = V3 / "ccs" / "ccs_results.csv"
    if cf.is_file():
        for _, r in pd.read_csv(cf).iterrows():
            if r.status != "COMPUTED":
                add(paradigm="CCS", cohort=r.cohort, endpoint=r.variant, model=r.variant,
                    feature_set="-", n=np.nan, events=np.nan, AUC=np.nan, AUC_lo95=np.nan,
                    AUC_hi95=np.nan, Brier=np.nan, validation="-",
                    leakage_status="n/a", quotable=False, note=str(r.get("reason", "")))
                continue
            add(paradigm="CCS", cohort=r.cohort, endpoint=r.variant,
                model=r.variant, feature_set="-", n=r.get("n"), events=r.get("events"),
                AUC=r.get("AUC_ml"), AUC_lo95=np.nan, AUC_hi95=np.nan, Brier=np.nan,
                validation="bootstrap CI (CCS-A) / MCD chi-square mapping (CCS-B)",
                leakage_status="n/a",
                quotable=True,
                note=(f"CCS {r.CCS:.3f} [{r.CCS_lo95:.3f}, {r.CCS_hi95:.3f}], threshold "
                      f"{r.threshold} - THRESHOLD UNCALIBRATED" if pd.notna(r.get("CCS"))
                      else f"median CCS_B {r.CCS_median:.3f}, "
                           f"{100 * r.fraction_flagged_outlying:.0f}% beyond chi-square cut "
                           "(cut not calibrated for MCD)"))

    # ---- feature-family comparison, if it has run --------------------------------------------------
    p15 = V3 / "p15" / "P15_feature_family_comparison.csv"
    if p15.is_file():
        for _, r in pd.read_csv(p15).iterrows():
            if r.get("status") != "COMPUTED":
                continue
            add(paradigm="L9 Feature-family comparison", cohort="TCIA multimodal",
                endpoint="loco-regional failure", model=r.model, feature_set=r.arm,
                n=r.get("n"), events=r.get("events"), AUC=r.get("cv_AUC"),
                AUC_lo95=r.get("auc_lo95"), AUC_hi95=r.get("auc_hi95"), Brier=r.get("Brier"),
                validation="5-fold x 5-repeat CV, selection inside folds",
                leakage_status="none - selection inside training folds", quotable=True,
                note=f"PR-AUC {r.get('PR_AUC')}, cal slope {r.get('cal_slope')}, "
                     f"sens {r.get('sensitivity')}, spec {r.get('specificity')}")

    df = pd.DataFrame(rows)
    df.insert(0, "analysis_date", date.today().isoformat())
    df.to_csv(O / "FINAL_MODEL_PERFORMANCE.csv", index=False)
    try:
        df.to_excel(O / "FINAL_MODEL_PERFORMANCE.xlsx", index=False)
    except Exception:
        pass
    print(f"{len(df)} model rows | quotable {int(df.quotable.sum())} | "
          f"leakage-flagged {int(df.leakage_status.str.contains('LEAKAGE').sum())}")
    print(df.groupby("paradigm").size().to_string())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
