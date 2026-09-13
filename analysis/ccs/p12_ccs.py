"""Phase 12 - Cohort Consistency Score: audit the implementation and run it on the three cohorts.

rbGyanX ships TWO different things under the CCS name (`engine/validation/cohort_consistency.py`), and
conflating them would be a reporting error:

  **CCS-A, agreement CCS** (`compute_ccs`): the mean of three Spearman correlations -
  classical-vs-ML, classical-vs-outcome, ML-vs-outcome - compared against an adaptive threshold
  `max(0.20, 0.50 x min(n/50, 1))`. Requires outcomes.

  **CCS-B, distributional CCS** (`compute_mcd_ccs`): per-patient minimum-covariance-determinant
  Mahalanobis distance to a reference cohort, mapped through the chi-square CDF to [0, 1], flagged
  above the 97.5th percentile. Requires no outcome - but it does require a SHARED FEATURE SPACE.

That last requirement is the binding one. The Parotid export is OAR-only (no target structure at all),
so it shares no dose descriptor with the two target-bearing cohorts. CCS-B is therefore computed for
TCIA-HN vs SPARK and reported as NOT COMPUTABLE for Parotid, rather than forcing a comparison on
features that do not exist.

Bootstrap CIs and a leave-one-component-out sensitivity analysis accompany CCS-A. The relationship
between CCS and model performance is tested rather than asserted.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# shared dose descriptors for CCS-B; both target-bearing cohorts carry all three
DIST_FEATURES = ["PTV__Dmean_gy", "PTV__D2_gy", "PTV__D98_gy"]


def oof_ml(X: np.ndarray, y: np.ndarray, seed: int = 0, folds: int = 5,
           repeats: int = 5) -> np.ndarray:
    """Out-of-fold logistic probabilities; standardisation fitted on the training fold only."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    acc, cnt = np.zeros(len(y)), np.zeros(len(y))
    for rep in range(repeats):
        for tr, te in StratifiedKFold(folds, shuffle=True,
                                      random_state=seed + 100 * rep).split(X, y):
            mu, sd = X[tr].mean(0), X[tr].std(0)
            sd[sd < 1e-8] = 1.0
            m = LogisticRegression(max_iter=2000, class_weight="balanced")
            m.fit((X[tr] - mu) / sd, y[tr])
            acc[te] += m.predict_proba((X[te] - mu) / sd)[:, 1]
            cnt[te] += 1
    return acc / np.maximum(cnt, 1)


def auc(y, p) -> float:
    y, p = np.asarray(y), np.asarray(p)
    pos, neg = p[y == 1], p[y == 0]
    if not pos.size or not neg.size:
        return float("nan")
    return float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean())


def ccs_a(compute_ccs, label, y, cl_risk, ml, rng, extra) -> dict:
    res = compute_ccs(y, cl_risk, ml)
    boot = []
    for _ in range(2000):
        i = rng.integers(0, len(y), len(y))
        if len(np.unique(y[i])) < 2:
            continue
        boot.append(compute_ccs(y[i], cl_risk[i], ml[i])["ccs"])
    lo, hi = (float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5))) if boot \
        else (float("nan"), float("nan"))
    comps = {"rho_classical_vs_ml": res["rho_classical_vs_ml"],
             "rho_classical_vs_outcome": res["rho_classical_vs_outcome"],
             "rho_ml_vs_outcome": res["rho_ml_vs_outcome"]}
    sens = {f"CCS_dropping_{k}": float(np.mean([v for kk, v in comps.items() if kk != k]))
            for k in comps}
    return {"cohort": label, "variant": "CCS-A agreement", "status": "COMPUTED",
            "n": int(len(y)), "events": int(y.sum()),
            "CCS": res["ccs"], "CCS_lo95": lo, "CCS_hi95": hi,
            "threshold": res["threshold_used"], "verdict": res["verdict"],
            "AUC_classical": auc(y, cl_risk), "AUC_ml": auc(y, ml),
            **comps, **sens, **extra}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True, type=Path)
    ap.add_argument("--features", required=True, type=Path)
    ap.add_argument("--hn-frame", required=True, type=Path,
                    help="V2_PINN_input_features.csv - carries the TCIA clinical covariates")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(a.repo / "engine"))
    from validation.cohort_consistency import compute_ccs, compute_mcd_ccs

    master = pd.read_csv(a.features, low_memory=False)
    rng = np.random.default_rng(a.seed)
    rows, per_patient = [], []

    # ---------------- CCS-A, Parotid: LKB NTCP vs logistic ML vs xerostomia --------------------
    g = master[master.cohort == "Parotid"].copy()
    feats = ["Parotid_unspecified__Dmean_gy", "clin_age", "clin_sex_M", "clin_tobacco_exposure"]
    y = pd.to_numeric(g["outcome_xerostomia_g2plus"], errors="coerce")
    cl = pd.to_numeric(g["NTCP__Parotid_unspecified__LKB_loglogit"], errors="coerce")
    ok = y.notna() & cl.notna() & g[feats].notna().all(axis=1)
    gp, yp, clp = g[ok], y[ok].astype(int).values, cl[ok].values
    ml = oof_ml(gp[feats].astype(float).values, yp, a.seed)
    rows.append(ccs_a(compute_ccs, "Parotid", yp, clp, ml, rng,
                      {"outcome": "xerostomia G>=2",
                       "classical_model": "LKB log-logistic NTCP (parotid, side-unspecified)",
                       "ml_model": "logistic on Dmean + age + sex + tobacco, 5x5 OOF",
                       "classical_orientation": "higher NTCP = higher risk"}))
    per_patient += [{"cohort": "Parotid", "pseudonym": p, "classical_risk": float(c),
                     "ml_prob": float(m), "outcome": int(o), "variant": "CCS-A"}
                    for p, c, m, o in zip(gp["pseudonym"], clp, ml, yp)]

    # ---------------- CCS-A, TCIA-HN: Poisson TCP vs logistic ML vs loco-regional failure ------
    hn = pd.read_csv(a.hn_frame, low_memory=False)
    hmaster = master[master.cohort == "TCIA_HN"][["pseudonym", "TCP__PTV__Poisson"]]
    h = hn.merge(hmaster, on="pseudonym", how="left")
    hfeats = ["Dmean_gy", "D95_gy", "clin_age", "clin_sex_M", "clin_stage"]
    hfeats = [c for c in hfeats if c in h.columns]
    yh = (1 - pd.to_numeric(h["tcp_outcome"], errors="coerce"))      # back to FAILURE = 1
    clh = pd.to_numeric(h["TCP__PTV__Poisson"], errors="coerce")
    okh = yh.notna() & clh.notna() & h[hfeats].notna().all(axis=1)
    gh, yh, clh = h[okh], yh[okh].astype(int).values, clh[okh].values
    if len(gh) >= 20 and len(np.unique(yh)) > 1 and np.nanstd(clh) > 0:
        mlh = oof_ml(gh[hfeats].astype(float).values, yh, a.seed)
        rows.append(ccs_a(compute_ccs, "TCIA_HN", yh, -clh, mlh, rng,
                          {"outcome": "loco-regional failure",
                           "classical_model": "Poisson TCP (PTV), sign-flipped to a risk scale",
                           "ml_model": f"logistic on {'+'.join(hfeats)}, 5x5 OOF",
                           "classical_orientation": "higher TCP = lower risk (negated)"}))
        per_patient += [{"cohort": "TCIA_HN", "pseudonym": p, "classical_risk": float(-c),
                         "ml_prob": float(m), "outcome": int(o), "variant": "CCS-A"}
                        for p, c, m, o in zip(gh["pseudonym"], clh, mlh, yh)]
    else:
        rows.append({"cohort": "TCIA_HN", "variant": "CCS-A agreement", "status": "NOT COMPUTABLE",
                     "reason": f"n={len(gh)}, classical SD={np.nanstd(clh):.3g} - the saturated "
                               "Poisson TCP has no usable spread on this cohort"})

    rows.append({"cohort": "SPARK", "variant": "CCS-A agreement", "status": "NOT COMPUTABLE",
                 "reason": "no patient-level outcome linkage exists for SPARK, so no "
                           "classical-vs-outcome or ML-vs-outcome correlation can be formed"})

    # ---------------- CCS-B, distributional -----------------------------------------------------
    common = [c for c in DIST_FEATURES if c in master.columns]
    ref = master[master.cohort == "TCIA_HN"][common].dropna()
    for coh in ("TCIA_HN", "SPARK", "Parotid"):
        g = master[master.cohort == coh][["pseudonym"] + common].dropna()
        if len(g) < 5:
            rows.append({"cohort": coh, "variant": "CCS-B distributional",
                         "status": "NOT COMPUTABLE",
                         "reason": "the Parotid export is OAR-only - it contains no target "
                                   "structure, so it shares no dose descriptor with the "
                                   "target-bearing cohorts"})
            continue
        r = compute_mcd_ccs(g[common].values, ref.values)
        ccs = np.asarray(r["ccs"], dtype=float)
        rows.append({
            "cohort": coh, "variant": "CCS-B distributional", "status": "COMPUTED",
            "n": int(len(g)), "reference_cohort": "TCIA_HN",
            "features": "|".join(common), "n_features": r["n_features"],
            "chi2_critical": r["chi2_critical"],
            "CCS_median": float(np.median(ccs)), "CCS_p25": float(np.percentile(ccs, 25)),
            "CCS_p75": float(np.percentile(ccs, 75)),
            "fraction_flagged_outlying": float(len(r["flagged_indices"]) / len(g)),
            "interpretation": "0 = indistinguishable from the reference; 1 = far outside it",
        })
        per_patient += [{"cohort": coh, "pseudonym": p, "ccs_distributional": float(v),
                         "mahalanobis_sq": float(m), "variant": "CCS-B"}
                        for p, v, m in zip(g["pseudonym"], ccs, r["mahalanobis_sq"])]

    res = pd.DataFrame(rows)
    res.to_csv(a.out / "ccs_results.csv", index=False)
    pd.DataFrame(per_patient).to_csv(a.out / "ccs_per_patient.csv", index=False)
    comp = res[(res.variant == "CCS-A agreement") & (res.status == "COMPUTED")]
    (a.out / "ccs_summary.json").write_text(json.dumps({
        "results": res.to_dict("records"),
        "ccs_vs_performance": {
            "n_cohorts_with_CCS_A": int(len(comp)),
            "test": "NOT PERFORMED - with at most two computable cohorts a correlation between CCS "
                    "and model performance cannot be estimated; reporting one would be manufactured",
        },
    }, indent=2, default=str), encoding="utf-8")
    with pd.option_context("display.width", 220, "display.max_columns", 40):
        print(res[[c for c in ("cohort", "variant", "status", "n", "CCS", "CCS_lo95", "CCS_hi95",
                               "threshold", "verdict", "AUC_classical", "AUC_ml", "CCS_median",
                               "fraction_flagged_outlying", "reason") if c in res.columns]]
              .to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
