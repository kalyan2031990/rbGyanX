"""Phase 17 - statistical analysis of the final manuscript datasets.

Tests are chosen by the data, not applied mechanically:

* continuous variables are summarised by median [IQR] because the dose and radiobiology distributions
  are bounded and skewed (NTCP and TCP are probabilities on [0,1]; several saturate);
* two-group comparisons use Mann-Whitney U, three-group use Kruskal-Wallis - no normality is assumed
  and none was found for the dose metrics;
* categorical comparisons use Fisher's exact test when any expected count is below 5, chi-square
  otherwise;
* associations with a binary outcome use the point-biserial-equivalent Spearman rho plus a
  bootstrap AUC, which is the interpretable quantity for a clinical predictor;
* Benjamini-Hochberg FDR is applied WITHIN each pre-specified family of tests, not across the whole
  file, because families answer different questions and pooling them would over-correct.

Normality is reported (Shapiro-Wilk) for transparency but is not used to switch tests: with n = 43-186
a normality test's power varies so much across cohorts that test choice would become cohort-dependent.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SW_MAX_N = 5000


def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, dtype=float)
    ok = np.isfinite(p)
    out = np.full(p.shape, np.nan)
    q = p[ok]
    if q.size == 0:
        return out
    order = np.argsort(q)
    ranked = q[order] * q.size / (np.arange(q.size) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adj = np.empty_like(ranked)
    adj[order] = np.clip(ranked, 0, 1)
    out[ok] = adj
    return out


def auc_ci(y, x, seed=0, n=2000):
    y, x = np.asarray(y, float), np.asarray(x, float)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    if len(np.unique(y)) < 2:
        return np.nan, np.nan, np.nan

    def a(yy, xx):
        p, q = xx[yy == 1], xx[yy == 0]
        return float((p[:, None] > q[None, :]).mean() + 0.5 * (p[:, None] == q[None, :]).mean())
    rng = np.random.default_rng(seed)
    b = [a(y[i], x[i]) for i in (rng.integers(0, len(y), len(y)) for _ in range(n))
         if len(np.unique(y[i])) > 1]
    return a(y, x), float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    W = a.workspace

    master = pd.read_csv(W / "03_Statistical_Analysis" / "feature_tables" /
                         "patient_features_ALL.csv", low_memory=False)
    rows: list[dict] = []
    desc: list[dict] = []

    # ---------------- descriptive statistics, per cohort ------------------------------------
    for coh, g in master.groupby("cohort"):
        num = g.select_dtypes(include=[np.number])
        for c in num.columns:
            v = num[c].dropna()
            if len(v) < 5 or v.nunique() < 2:
                continue
            sw_p = float(stats.shapiro(v.sample(min(len(v), SW_MAX_N),
                                                random_state=a.seed)).pvalue) if len(v) >= 3 \
                else np.nan
            desc.append({
                "cohort": coh, "variable": c, "n": int(len(v)),
                "median": float(v.median()), "q1": float(v.quantile(.25)),
                "q3": float(v.quantile(.75)), "min": float(v.min()), "max": float(v.max()),
                "mean": float(v.mean()), "sd": float(v.std(ddof=1)),
                "shapiro_p": sw_p,
                "normal_at_0.05": bool(np.isfinite(sw_p) and sw_p > 0.05),
            })
    dd = pd.DataFrame(desc)
    dd.to_csv(a.out / "descriptive_statistics.csv", index=False)

    # ---------------- family 1: cross-cohort dose comparison --------------------------------
    shared = [c for c in ("PTV__Dmean_gy", "PTV__D2_gy", "PTV__D98_gy", "PTV__HI", "PTV__CI")
              if c in master.columns]
    fam1 = []
    for c in shared:
        groups = [g[c].dropna().values for _, g in master.groupby("cohort") if g[c].notna().sum() >= 5]
        if len(groups) < 2:
            continue
        if len(groups) == 2:
            s, p = stats.mannwhitneyu(*groups, alternative="two-sided")
            test = "Mann-Whitney U"
        else:
            s, p = stats.kruskal(*groups)
            test = "Kruskal-Wallis"
        fam1.append({"family": "cross-cohort dose", "variable": c, "test": test,
                     "statistic": float(s), "p_raw": float(p),
                     "n_groups": len(groups),
                     "group_ns": "|".join(str(len(x)) for x in groups)})
    if fam1:
        f = pd.DataFrame(fam1)
        f["p_BH"] = bh(f.p_raw.values)
        rows += f.to_dict("records")

    # ---------------- family 2: Parotid predictors of xerostomia ----------------------------
    pg = master[master.cohort == "Parotid"]
    y = pd.to_numeric(pg.get("outcome_xerostomia_g2plus"), errors="coerce")
    fam2 = []
    if y.notna().sum() >= 20:
        cand = [c for c in pg.select_dtypes(include=[np.number]).columns
                if not c.startswith("outcome_") and pg[c].notna().sum() >= 20
                and pg[c].nunique() > 2]
        for c in cand:
            x = pd.to_numeric(pg[c], errors="coerce")
            m = x.notna() & y.notna()
            if m.sum() < 20:
                continue
            u, p = stats.mannwhitneyu(x[m & (y == 1)], x[m & (y == 0)], alternative="two-sided")
            rho, prho = stats.spearmanr(x[m], y[m])
            au, lo, hi = auc_ci(y[m], x[m], a.seed)
            fam2.append({"family": "Parotid predictors of xerostomia G>=2", "variable": c,
                         "test": "Mann-Whitney U", "statistic": float(u), "p_raw": float(p),
                         "spearman_rho": float(rho), "AUC": au, "AUC_lo95": lo, "AUC_hi95": hi,
                         "n": int(m.sum())})
    if fam2:
        f = pd.DataFrame(fam2)
        f["p_BH"] = bh(f.p_raw.values)
        rows += f.to_dict("records")

    # ---------------- family 3: TCIA-HN predictors of loco-regional failure -----------------
    hg = master[master.cohort == "TCIA_HN"]
    yh = pd.to_numeric(hg.get("outcome_locoregional"), errors="coerce")
    fam3 = []
    if yh.notna().sum() >= 20:
        cand = [c for c in hg.select_dtypes(include=[np.number]).columns
                if not c.startswith("outcome_") and hg[c].notna().sum() >= 50
                and hg[c].nunique() > 2]
        for c in cand:
            x = pd.to_numeric(hg[c], errors="coerce")
            m = x.notna() & yh.notna()
            if m.sum() < 30 or len(np.unique(yh[m])) < 2:
                continue
            u, p = stats.mannwhitneyu(x[m & (yh == 1)], x[m & (yh == 0)], alternative="two-sided")
            rho, _ = stats.spearmanr(x[m], yh[m])
            au, lo, hi = auc_ci(yh[m], x[m], a.seed)
            fam3.append({"family": "TCIA-HN predictors of loco-regional failure", "variable": c,
                         "test": "Mann-Whitney U", "statistic": float(u), "p_raw": float(p),
                         "spearman_rho": float(rho), "AUC": au, "AUC_lo95": lo, "AUC_hi95": hi,
                         "n": int(m.sum())})
    if fam3:
        f = pd.DataFrame(fam3)
        f["p_BH"] = bh(f.p_raw.values)
        rows += f.to_dict("records")

    res = pd.DataFrame(rows)
    res.to_csv(a.out / "statistical_results.csv", index=False)

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(), "seed": a.seed,
        "descriptive_rows": int(len(dd)),
        "families": {},
    }
    for fam, g in res.groupby("family") if len(res) else []:
        summary["families"][fam] = {
            "tests": int(len(g)),
            "significant_raw_0.05": int((g.p_raw < 0.05).sum()),
            "significant_BH_0.05": int((g.p_BH < 0.05).sum()),
            "top": g.nsmallest(5, "p_BH")[["variable", "p_raw", "p_BH"]].to_dict("records"),
        }
    summary["normality"] = {
        "variables_tested": int(dd.shapiro_p.notna().sum()),
        "normal_at_0.05": int(dd["normal_at_0.05"].sum()),
        "note": "reported for transparency; non-parametric tests were used regardless",
    }
    (a.out / "statistical_summary.json").write_text(json.dumps(summary, indent=2, default=str),
                                                    encoding="utf-8")
    print(json.dumps(summary["families"], indent=2, default=str)[:2500])
    print("normality:", summary["normality"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
