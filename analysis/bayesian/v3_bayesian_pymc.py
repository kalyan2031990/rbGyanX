"""FINAL_V3 Upgrade A - genuine Bayesian LKB/NTCP inference with PyMC.

What the previous analysis actually was
---------------------------------------
`fit_lkb_bayesian` fell back to a **bootstrap maximum-likelihood** path because PyMC was absent. It
produced a point estimate with percentile CONFIDENCE intervals. It is a legitimate frequentist result
and is retained here as the comparator, but it is not Bayesian and is never labelled as such.

The model
---------
LKB with a log-logistic link, the same functional form the engine uses so the posterior is directly
comparable with the deterministic NTCP:

    NTCP_i = 1 / (1 + (TD50 / gEUD_i)^(4*gamma50))
    y_i ~ Bernoulli(NTCP_i)

Priors (weakly informative, justified in BAYESIAN_METHOD_REPORT.md):
    TD50    ~ Lognormal(log(35), 0.5)   -> 95% mass roughly 13-95 Gy, centred near QUANTEC
    gamma50 ~ Lognormal(log(1.0), 0.6)  -> positive by construction, wide over plausible slopes

Cohort applicability is decided by the data, not by convenience: only Parotid pairs an organ dose with
an organ-specific toxicity endpoint. SPARK has no patient-level outcome linkage, so no Bayesian model
is fitted to it. The TCIA-HN organ-vs-tumour pairings remain exploratory and are not fitted here.
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 0
CHAINS = 4
DRAWS = 2000
TUNE = 2000
TARGET_ACCEPT = 0.95

PRIORS = {
    "reference": {"td50_mu": np.log(35.0), "td50_sd": 0.50,
                  "g50_mu": np.log(1.0), "g50_sd": 0.60,
                  "rationale": "centred near the QUANTEC parotid TD50 of ~39.9 Gy but wide "
                               "(95% ~13-95 Gy); slope positive by construction and only weakly "
                               "constrained"},
    "vague": {"td50_mu": np.log(35.0), "td50_sd": 1.00,
              "g50_mu": np.log(1.0), "g50_sd": 1.00,
              "rationale": "deliberately uninformative - tests whether the posterior is "
                           "prior-driven"},
    "quantec_tight": {"td50_mu": np.log(39.9), "td50_sd": 0.20,
                      "g50_mu": np.log(1.0), "g50_sd": 0.40,
                      "rationale": "strongly informed by QUANTEC; the opposite extreme"},
    "low_centre": {"td50_mu": np.log(28.4), "td50_sd": 0.50,
                   "g50_mu": np.log(0.6), "g50_sd": 0.60,
                   "rationale": "centred on the engine's configured log-logistic defaults "
                                "(TD50 28.4 Gy, gamma50 0.6)"},
}


def build_and_sample(geud, y, pri, draws=DRAWS, tune=TUNE, chains=CHAINS, seed=SEED):
    import pymc as pm
    import pytensor.tensor as pt
    with pm.Model() as model:
        td50 = pm.Lognormal("TD50", mu=pri["td50_mu"], sigma=pri["td50_sd"])
        g50 = pm.Lognormal("gamma50", mu=pri["g50_mu"], sigma=pri["g50_sd"])
        # log-logistic LKB, evaluated in log space for numerical stability
        logit_p = 4.0 * g50 * (pt.log(geud) - pt.log(td50))
        p = pm.Deterministic("ntcp", pm.math.sigmoid(logit_p))
        pm.Bernoulli("obs", p=p, observed=y)
        idata = pm.sample(draws=draws, tune=tune, chains=chains, cores=1,
                          target_accept=TARGET_ACCEPT, random_seed=seed,
                          progressbar=False)
        # ArviZ >= 1.0 returns an xarray DataTree, which has no .extend(); PyMC writes the groups
        # in place instead
        pm.compute_log_likelihood(idata, progressbar=False)
        prior = pm.sample_prior_predictive(draws=1000, random_seed=seed)
        for grp in ("prior", "prior_predictive"):
            if grp in prior.children:
                idata[grp] = prior[grp]
        pm.sample_posterior_predictive(idata, random_seed=seed, progressbar=False,
                                       extend_inferencedata=True)
    return model, idata


def hdi95(x) -> tuple[float, float]:
    """95% highest-density interval. ArviZ 1.x moved `hdi`, so compute it directly - the shortest
    interval containing 95% of the sorted draws."""
    x = np.sort(np.asarray(x).ravel())
    n = len(x)
    k = int(np.floor(0.95 * n))
    if k < 1 or k >= n:
        return float(x[0]), float(x[-1])
    widths = x[k:] - x[:n - k]
    i = int(np.argmin(widths))
    return float(x[i]), float(x[i + k])


def diagnostics(idata) -> pd.DataFrame:
    import arviz as az
    s = az.summary(idata, var_names=["TD50", "gamma50"], ci_prob=0.95, round_to=6)
    s = s.reset_index().rename(columns={"index": "parameter"})
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    a = ap.parse_args()
    W, O = a.workspace, a.out
    (O / "figures").mkdir(parents=True, exist_ok=True)
    (O / "tables").mkdir(parents=True, exist_ok=True)

    import arviz as az
    import pymc as pm

    master = pd.read_csv(W / "03_Statistical_Analysis" / "feature_tables" /
                         "patient_features_ALL.csv", low_memory=False)
    g = master[master.cohort == "Parotid"].copy()
    # gEUD with a=1 for a parallel mean-dose endpoint reduces to the mean dose, which is what the
    # engine uses for this organ; use the same quantity so the posterior is comparable
    dose = pd.to_numeric(g["Parotid_unspecified__Dmean_gy"], errors="coerce")
    y = pd.to_numeric(g["outcome_xerostomia_g2plus"], errors="coerce")
    ok = dose.notna() & y.notna() & (dose > 0)
    geud = dose[ok].values.astype(float)
    yy = y[ok].values.astype(int)
    print(f"Parotid: n={len(yy)}, events={int(yy.sum())}, "
          f"gEUD {geud.min():.1f}-{geud.max():.1f} Gy", flush=True)

    results, diags, sens = [], [], []
    idatas = {}

    for name, pri in PRIORS.items():
        print(f"sampling prior='{name}' ...", flush=True)
        _, idata = build_and_sample(geud, yy, pri)
        idatas[name] = idata
        d = diagnostics(idata)
        d.insert(0, "prior", name)
        diags.append(d)

        post = idata.posterior
        td = post["TD50"].values.ravel()
        gm = post["gamma50"].values.ravel()
        hdi_td = hdi95(td)
        hdi_gm = hdi95(gm)
        # ArviZ 1.x returns DataTrees from rhat/ess; the summary frame already carries the
        # diagnostics as columns, so read them from there instead of unwrapping the tree
        rhat = float(pd.to_numeric(d["r_hat"], errors="coerce").max())
        ess_b = float(pd.to_numeric(d["ess_bulk"], errors="coerce").min())
        ess_t = float(pd.to_numeric(d["ess_tail"], errors="coerce").min())
        div = int(idata.sample_stats["diverging"].values.sum())
        converged = bool(rhat < 1.01 and ess_b > 400 and div == 0)

        row = {
            "prior": name, "cohort": "Parotid", "endpoint": "xerostomia G>=2",
            "n": len(yy), "events": int(yy.sum()),
            "method": "Bayesian posterior inference (PyMC NUTS)",
            "TD50_posterior_median": float(np.median(td)),
            "TD50_posterior_mean": float(td.mean()),
            "TD50_HDI95_low": float(hdi_td[0]), "TD50_HDI95_high": float(hdi_td[1]),
            "gamma50_posterior_median": float(np.median(gm)),
            "gamma50_HDI95_low": float(hdi_gm[0]), "gamma50_HDI95_high": float(hdi_gm[1]),
            "posterior_corr_TD50_gamma50": float(np.corrcoef(td, gm)[0, 1]),
            "max_rhat": rhat, "min_ess_bulk": ess_b, "min_ess_tail": ess_t,
            "divergences": div, "converged": converged,
            "interval_type": "95% highest-density CREDIBLE interval",
            "chains": CHAINS, "draws": DRAWS, "tune": TUNE,
            "target_accept": TARGET_ACCEPT, "seed": SEED,
            "prior_rationale": pri["rationale"],
        }
        results.append(row)
        sens.append({"prior": name, "td50_prior_median_gy": float(np.exp(pri["td50_mu"])),
                     "td50_prior_sd_log": pri["td50_sd"],
                     "gamma50_prior_median": float(np.exp(pri["g50_mu"])),
                     "gamma50_prior_sd_log": pri["g50_sd"],
                     "TD50_posterior_median": row["TD50_posterior_median"],
                     "TD50_HDI95": f"{row['TD50_HDI95_low']:.2f}-{row['TD50_HDI95_high']:.2f}",
                     "gamma50_posterior_median": row["gamma50_posterior_median"],
                     "converged": converged, "rationale": pri["rationale"]})
        print(f"   TD50 {row['TD50_posterior_median']:.2f} "
              f"[{row['TD50_HDI95_low']:.2f}, {row['TD50_HDI95_high']:.2f}] | "
              f"rhat {rhat:.4f} | ess {ess_b:.0f} | div {div}", flush=True)

    ref = idatas["reference"]
    pd.DataFrame(results).to_csv(O / "BAYESIAN_FINAL_RESULTS.csv", index=False)
    pd.concat(diags, ignore_index=True).to_csv(O / "BAYESIAN_DIAGNOSTICS.csv", index=False)
    pd.DataFrame(sens).to_csv(O / "BAYESIAN_PRIOR_SENSITIVITY.csv", index=False)

    # posterior summary of the reference model, including the fitted dose-response curve
    post = ref.posterior
    td = post["TD50"].values.ravel()
    gm = post["gamma50"].values.ravel()
    grid = np.linspace(max(geud.min() * 0.6, 1.0), geud.max() * 1.2, 60)
    curve = []
    for d_ in grid:
        p = 1.0 / (1.0 + (td / d_) ** (4.0 * gm))
        curve.append({"dose_gy": float(d_), "ntcp_median": float(np.median(p)),
                      "ntcp_hdi95_low": hdi95(p)[0], "ntcp_hdi95_high": hdi95(p)[1]})
    pd.DataFrame(curve).to_csv(O / "BAYESIAN_POSTERIOR_SUMMARY.csv", index=False)

    # posterior predictive: per-patient predicted event probability and interval
    ppc = ref.posterior_predictive["obs"].values.reshape(-1, len(yy))
    ntcp = ref.posterior["ntcp"].values.reshape(-1, len(yy))
    pp = pd.DataFrame({
        "pseudonym": g.loc[ok, "pseudonym"].values,
        "gEUD_gy": geud, "observed": yy,
        "ntcp_posterior_median": np.median(ntcp, axis=0),
        "ntcp_hdi95_low": [hdi95(ntcp[:, i])[0] for i in range(len(yy))],
        "ntcp_hdi95_high": [hdi95(ntcp[:, i])[1] for i in range(len(yy))],
        "posterior_predictive_event_rate": ppc.mean(axis=0),
    })
    pp.to_csv(O / "BAYESIAN_POSTERIOR_PREDICTIVE.csv", index=False)

    # posterior predictive check at cohort level
    obs_rate = float(yy.mean())
    rep_rate = ppc.mean(axis=1)
    ppp = float((rep_rate >= obs_rate).mean())
    try:
        loo = az.loo(ref)
    except Exception as exc:
        loo = None
        print(f"LOO unavailable in this ArviZ build: {type(exc).__name__}", flush=True)
    ppc_summary = {
        "observed_event_rate": obs_rate,
        "ppc_replicated_mean": float(rep_rate.mean()),
        "ppc_replicated_HDI95": list(hdi95(rep_rate)),
        "posterior_predictive_p_value": ppp,
        "ppc_interpretation": ("a p-value near 0.5 indicates the model reproduces the observed "
                               "event rate; values near 0 or 1 indicate misfit"),
        "loo_elpd": float(loo.elpd_loo) if loo is not None and hasattr(loo, "elpd_loo") else None,
        "loo_se": float(loo.se) if loo is not None and hasattr(loo, "se") else None,
    }

    # ---- figures ----------------------------------------------------------------------------
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.dpi": 150, "savefig.bbox": "tight", "font.size": 9})

    az.plot_trace(ref, var_names=["TD50", "gamma50"])
    plt.gcf().suptitle("Bayesian LKB - trace and marginal posteriors (reference prior)", y=1.02)
    for ext in (".png", ".svg"):
        plt.savefig(O / "figures" / f"FigB1_trace{ext}")
    plt.close("all")

    fig, ax = plt.subplots(figsize=(6.2, 4.2))
    c = pd.DataFrame(curve)
    ax.fill_between(c.dose_gy, c.ntcp_hdi95_low, c.ntcp_hdi95_high, alpha=0.25,
                    color="#1b6ca8", label="95 % credible band")
    ax.plot(c.dose_gy, c.ntcp_median, color="#1b6ca8", lw=2, label="posterior median")
    jitter = (np.random.default_rng(0).random(len(yy)) - 0.5) * 0.04
    ax.plot(geud, yy + jitter, "o", ms=4, color="#c0392b", alpha=0.6, label="observed")
    ax.axvline(34.4, ls=":", color="0.4", lw=1.2)
    ax.text(34.6, 0.05, "bootstrap-MLE TD50 34.4", fontsize=7.5, color="0.35")
    ax.set_xlabel("Parotid mean dose (Gy)")
    ax.set_ylabel("P(xerostomia G$\\geq$2)")
    ax.set_title("Bayesian LKB dose-response, Parotid (n = 54, 34 events)", fontsize=10)
    ax.legend(fontsize=8)
    for ext in (".png", ".svg"):
        fig.savefig(O / "figures" / f"FigB2_dose_response{ext}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    ax.hist(rep_rate, bins=30, color="#8ab4d8", edgecolor="white")
    ax.axvline(obs_rate, color="#c0392b", lw=2, label=f"observed {obs_rate:.3f}")
    ax.set_xlabel("replicated cohort event rate")
    ax.set_ylabel("posterior draws")
    ax.set_title(f"Posterior predictive check (Bayesian p = {ppp:.3f})", fontsize=10)
    ax.legend(fontsize=8)
    for ext in (".png", ".svg"):
        fig.savefig(O / "figures" / f"FigB3_posterior_predictive{ext}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    ax.plot(td, gm, ".", ms=1.5, alpha=0.25, color="#1b6ca8")
    ax.set_xlabel("TD50 (Gy)")
    ax.set_ylabel("gamma50")
    ax.set_title(f"Joint posterior (r = {np.corrcoef(td, gm)[0, 1]:.3f})", fontsize=10)
    for ext in (".png", ".svg"):
        fig.savefig(O / "figures" / f"FigB4_joint_posterior{ext}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    s = pd.DataFrame(sens)
    yy_ = np.arange(len(s))
    ax.errorbar(s.TD50_posterior_median, yy_,
                xerr=[s.TD50_posterior_median - [float(x.split("-")[0]) for x in s.TD50_HDI95],
                      [float(x.split("-")[1]) for x in s.TD50_HDI95] - s.TD50_posterior_median],
                fmt="o", color="#1b6ca8", capsize=3)
    ax.axvline(39.9, color="#2e7d32", ls="--", lw=1.2, label="QUANTEC 39.9 Gy")
    ax.axvline(34.4, color="#c0392b", ls=":", lw=1.2, label="bootstrap-MLE 34.4 Gy")
    ax.set_yticks(yy_)
    ax.set_yticklabels(s.prior)
    ax.set_xlabel("TD50 posterior median with 95 % HDI (Gy)")
    ax.set_title("Prior sensitivity", fontsize=10)
    ax.legend(fontsize=8)
    for ext in (".png", ".svg"):
        fig.savefig(O / "figures" / f"FigB5_prior_sensitivity{ext}")
    plt.close(fig)

    (O / "tables").mkdir(exist_ok=True)
    pd.DataFrame(results).to_csv(O / "tables" / "TableB_bayesian_results.csv", index=False)
    pd.DataFrame(sens).to_csv(O / "tables" / "TableB_prior_sensitivity.csv", index=False)

    (O / "BAYESIAN_PPC_SUMMARY.json").write_text(json.dumps(ppc_summary, indent=2),
                                                 encoding="utf-8")
    meta = {"generated": date.today().isoformat(), "pymc": pm.__version__,
            "arviz": az.__version__, "seed": SEED, "chains": CHAINS, "draws": DRAWS,
            "tune": TUNE, "target_accept": TARGET_ACCEPT,
            "sampler": "NUTS (PyMC default)",
            "cohorts_fitted": ["Parotid"],
            "cohorts_not_fitted": {
                "SPARK": "no patient-level outcome linkage exists",
                "TCIA_HN": "organ dose vs tumour/survival endpoint - not an NTCP dose-response; "
                           "remains EXPLORATORY and is not fitted"},
            "ppc": ppc_summary, "results": results}
    (O / "BAYESIAN_RUN_MANIFEST.json").write_text(json.dumps(meta, indent=2, default=str),
                                                  encoding="utf-8")
    print("\nposterior predictive:", json.dumps(ppc_summary, indent=2)[:400])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
