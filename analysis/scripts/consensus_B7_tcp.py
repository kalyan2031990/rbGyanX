"""
Analysis B7 — does the inverse-variance 1/sigma^2 pathology generalise to the TCP model family?

A registered-prediction test (see analysis/preregistration_B.md Amendment 5, committed before this ran).
Wires the engine TCP family (Poisson-LQ, Zaider-Minerbo, gEUD-logistic, logistic;
uncertainty.parameter_mc.run_parameter_mc + HN TCPSiteParams) into the same consensus/comparator harness
used for NTCP. Models are used EXACTLY as implemented — no numerics changed. Per-patient PTV DVH is
reconstructed from reported dose moments (truncated-normal(Dmean, dose_std), 40 bins); a pre-registered
approximation. Reads the private HN cohort locally; writes ONLY pseudonymised aggregate results to the
gitignored analysis/outputs/consensus_B7_tcp/. Seed 0 everywhere.

Run:
  python analysis/scripts/consensus_B7_tcp.py --data-root "C:/.../validation_study"
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# reuse the exact metric + bootstrap helpers from the NTCP analysis (no re-implementation)
from consensus_B import (  # noqa: E402
    EPS,
    _logit,
    _sigmoid,
    all_metrics,
    brier,
    cal_slope_intercept,
)

from config.site_params import load_site_params  # noqa: E402
from uncertainty.inverse_variance_consensus import inverse_variance_consensus  # noqa: E402
from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc  # noqa: E402

SEED = 0
N_MC = 2000
N_BOOT = 2000
OUT = Path(__file__).resolve().parents[1] / "outputs" / "consensus_B7_tcp"
TCP_MODELS = ["Poisson", "ZM", "gEUD", "Logistic"]
_KEY = {"Poisson": "TCP_Poisson_mc", "ZM": "TCP_ZM_mc", "gEUD": "TCP_gEUD_mc",
        "Logistic": "TCP_Logistic_mc"}


@dataclass
class PatientPred:
    pseudonym: str
    control: int  # 1 = loco-regional control, 0 = failure
    centre: str
    est: dict
    sd: dict


def reconstruct_ptv_dvh(dmean: float, dstd: float, nbins: int = 40) -> pd.DataFrame:
    """Per-pre-registration: truncated-normal(Dmean, dose_std) differential PTV DVH, 40 physical-dose
    bins, volume_frac normalised to 1. Near-homogeneous PTVs make this tightly constrained."""
    if not np.isfinite(dstd) or dstd <= 0.1:
        return pd.DataFrame({"dose_gy": [float(dmean)], "volume_frac": [1.0]})
    lo, hi = max(0.0, dmean - 4 * dstd), dmean + 4 * dstd
    edges = np.linspace(lo, hi, nbins + 1)
    mids = 0.5 * (edges[:-1] + edges[1:])
    w = norm.pdf(mids, dmean, dstd)
    w = w / w.sum()
    return pd.DataFrame({"dose_gy": mids, "volume_frac": w})


def load_cohort(root: Path) -> pd.DataFrame:
    df = pd.read_csv(root / "derived" / "hn_cohort_features.csv")
    need = ["patient_id", "n_fractions", "PTV_Dmean_gy", "PTV_dose_std_gy", "locoregional", "centre"]
    miss = [c for c in need if c not in df.columns]
    if miss:
        raise SystemExit(f"HN cohort missing columns: {miss}; STOP.")
    df = df[df["locoregional"].notna() & df["PTV_Dmean_gy"].notna()].reset_index(drop=True)
    return df


def per_patient_predictions(cohort: pd.DataFrame) -> list[PatientPred]:
    sp = load_site_params("HN")
    cfg = ParamUncertaintyConfig(n_samples=N_MC, seed=SEED)
    preds: list[PatientPred] = []
    for i, r in cohort.iterrows():
        dvh = reconstruct_ptv_dvh(float(r["PTV_Dmean_gy"]), float(r["PTV_dose_std_gy"]))
        nfx = int(r["n_fractions"]) if np.isfinite(r["n_fractions"]) else 35
        try:
            mc = run_parameter_mc(dvh, nfx, sp, target_type="GTV", config=cfg)
        except Exception as exc:
            print(f"  [excluded] patient#{i}: {type(exc).__name__}")
            continue
        est, sd = {}, {}
        ok = True
        for m in TCP_MODELS:
            blk = mc.get(_KEY[m], {})
            mean, s = blk.get("mean", math.nan), blk.get("sd", math.nan)
            # allow sigma == 0 (e.g. Logistic: its params are not in the MC set) — the engine's
            # inverse_variance_consensus masks var>0, so a sigma=0 model is dropped from IVW. We keep
            # its point estimate for single-model / naive / median comparators and record sigma=0.
            if not (math.isfinite(mean) and math.isfinite(s) and s >= 0):
                ok = False
                break
            est[m], sd[m] = float(mean), max(float(s), 0.0)
        if not ok:
            print(f"  [excluded] patient#{i}: non-finite TCP MC")
            continue
        control = 1 - int(r["locoregional"])  # 1 = controlled
        preds.append(PatientPred(f"HN-{i:03d}", control, str(r.get("centre", "NA")), est, sd))
    return preds


def _ivw(est: dict, sd: dict) -> float:
    return inverse_variance_consensus([est[m] for m in TCP_MODELS],
                                      [sd[m] ** 2 for m in TCP_MODELS])["mean"]


def comparator_predictions(preds: list[PatientPred]) -> dict[str, np.ndarray]:
    y = np.array([p.control for p in preds])
    out: dict[str, np.ndarray] = {}
    for m in TCP_MODELS:
        out[m] = np.array([p.est[m] for p in preds])
    stack = np.column_stack([out[m] for m in TCP_MODELS])
    out["naive_mean_prob"] = np.nanmean(stack, axis=1)
    out["naive_mean_logit"] = _sigmoid(np.nanmean(_logit(stack), axis=1))
    out["consensus"] = np.array([_ivw(p.est, p.sd) for p in preds])
    out["median"] = np.array([float(np.median([p.est[m] for m in TCP_MODELS])) for p in preds])
    best = min(TCP_MODELS, key=lambda m: brier(y, out[m]))
    out[f"best_single({best})"] = out[best]
    return out


def _ivw_weight_fractions(sd: dict) -> dict:
    """1/sigma^2 weight fractions the way the engine forms them: models with sigma<=0 are MASKED out
    (var>0 filter) and get weight 0 — an infinitely-confident member is paradoxically excluded."""
    v = np.array([sd[m] ** 2 for m in TCP_MODELS])
    mask = v > 0
    wf = {m: 0.0 for m in TCP_MODELS}
    if mask.any():
        w = np.where(mask, 1.0 / np.where(mask, v, 1.0), 0.0)
        w = w / w.sum()
        for j, m in enumerate(TCP_MODELS):
            wf[m] = float(w[j])
    return wf


def weight_distribution(preds: list[PatientPred]) -> pd.DataFrame:
    """B7.3 / B9-analogue: spontaneous 1/sigma^2 weight fraction per TCP model (no adversary)."""
    rows = []
    wfs = [_ivw_weight_fractions(p.sd) for p in preds]
    for m in TCP_MODELS:
        sds = np.array([p.sd[m] for p in preds])
        ests = np.array([p.est[m] for p in preds])
        rows.append({"model": m, "sigma_median": float(np.median(sds)),
                     "sigma_iqr": float(np.subtract(*np.percentile(sds, [75, 25]))),
                     "frac_patients_sigma_zero": float(np.mean(sds <= 0)),
                     "mean_weight_fraction": float(np.mean([w[m] for w in wfs])),
                     "pred_median": float(np.median(ests)), "pred_std": float(ests.std())})
    return pd.DataFrame(rows)


def bootstrap_paired(y, preds_dict, ref="consensus", n=N_BOOT, seed=SEED):
    rng = np.random.default_rng(seed)
    y = np.asarray(y, int)
    idx_pos, idx_neg = np.where(y == 1)[0], np.where(y == 0)[0]
    comps = [k for k in preds_dict if k != ref]
    metrics = ["brier", "ece", "auc", "cal_slope"]
    diffs = {c: {m: [] for m in metrics} for c in comps}
    for _ in range(n):
        bi = np.concatenate([rng.choice(idx_pos, len(idx_pos), replace=True),
                             rng.choice(idx_neg, len(idx_neg), replace=True)])
        yb = y[bi]
        ref_m = all_metrics(yb, preds_dict[ref][bi])
        for c in comps:
            cm = all_metrics(yb, preds_dict[c][bi])
            for mth in metrics:
                if mth == "cal_slope":
                    diffs[c][mth].append(abs(ref_m[mth] - 1) - abs(cm[mth] - 1))
                else:
                    diffs[c][mth].append(ref_m[mth] - cm[mth])
    rows = []
    for c in comps:
        for mth in metrics:
            arr = np.array(diffs[c][mth], float)
            arr = arr[np.isfinite(arr)]
            if len(arr) == 0:
                rows.append({"comparator": c, "metric": mth, "ref_minus_comparator": math.nan,
                             "ci_lo": math.nan, "ci_hi": math.nan, "ci_excludes_0": False})
                continue
            lo, hi = np.percentile(arr, [2.5, 97.5])
            rows.append({"comparator": c, "metric": mth, "ref_minus_comparator": float(np.mean(arr)),
                         "ci_lo": float(lo), "ci_hi": float(hi),
                         "ci_excludes_0": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(rows)


def interval_quality(preds: list[PatientPred], n_groups=5):
    y = np.array([p.control for p in preds])
    zmap = {50: 0.674, 80: 1.282, 95: 1.960}
    rows = []
    for m in TCP_MODELS + ["consensus"]:
        if m == "consensus":
            means = np.array([_ivw(p.est, p.sd) for p in preds])
            sds = np.array([math.sqrt(inverse_variance_consensus(
                [p.est[k] for k in TCP_MODELS], [p.sd[k] ** 2 for k in TCP_MODELS])["variance"])
                for p in preds])
        else:
            means = np.array([p.est[m] for p in preds])
            sds = np.array([p.sd[m] for p in preds])
        order = np.argsort(means)
        groups = np.array_split(order, n_groups)
        for lvl, z in zmap.items():
            covered, widths = 0, []
            for g in groups:
                obs = y[g].mean()
                lo = np.clip(means[g].mean() - z * sds[g].mean(), 0, 1)
                hi = np.clip(means[g].mean() + z * sds[g].mean(), 0, 1)
                widths.append(hi - lo)
                covered += int(lo <= obs <= hi)
            rows.append({"model": m, "nominal_pct": lvl, "empirical_coverage": covered / len(groups),
                         "mean_band_width": float(np.mean(widths))})
    return pd.DataFrame(rows)


def stress_and_repairs(preds: list[PatientPred], poison_model: str):
    """B4 stress + B5 repairs on the TCP family. Poison `poison_model` (shift its TCP down the logit +
    narrow its band); map weight captured and consensus Brier damage; compare IVW / disagreement / median."""
    base = [{"c": p.control, "est": dict(p.est), "sd": dict(p.sd)} for p in preds]
    y = np.array([b["c"] for b in base])

    def poison(b, shift, narrow):
        est, sd = dict(b["est"]), dict(b["sd"])
        est[poison_model] = float(np.clip(_sigmoid(_logit(est[poison_model]) - 6.0 * shift), EPS, 1 - EPS))
        sd[poison_model] = sd[poison_model] * narrow
        return est, sd

    def combine(est, sd, method):
        e = np.array([est[m] for m in TCP_MODELS])
        v = np.array([sd[m] ** 2 for m in TCP_MODELS])
        if method == "median":
            return float(np.median(e)), math.nan
        if method == "disagreement":
            v = v + float(np.var(e, ddof=1))
        c = inverse_variance_consensus(e.tolist(), v.tolist())
        # poisoned model's weight via the masking-aware helper (robust to sigma=0 members being dropped)
        wbad = _ivw_weight_fractions({m: math.sqrt(v[j]) for j, m in enumerate(TCP_MODELS)})[poison_model]
        return c["mean"], wbad

    base_cons = np.array([combine(b["est"], b["sd"], "naive_ivw")[0] for b in base])
    base_brier = brier(y, base_cons)
    stress_rows = []
    for shift in (0.0, 0.10, 0.25, 0.50):
        for narrow in (1.0, 0.5, 0.2, 0.1):
            preds_v, ws = [], []
            for b in base:
                est, sd = poison(b, shift, narrow)
                mean, wbad = combine(est, sd, "naive_ivw")
                preds_v.append(mean)
                ws.append(wbad)
            m = all_metrics(y, np.array(preds_v))
            stress_rows.append({"poisoned_model": poison_model, "td50_shift_frac": shift,
                                "sd_narrow_factor": narrow, "bad_model_weight": float(np.nanmean(ws)),
                                "consensus_brier": m["brier"],
                                "brier_damage_vs_clean": m["brier"] - base_brier,
                                "consensus_cal_slope": m["cal_slope"]})
    repair_rows = []
    for label, (shift, narrow) in {"clean": (0.0, 1.0), "worst_poison": (0.50, 0.1)}.items():
        for method in ("naive_ivw", "disagreement", "median"):
            preds_v = [combine(*poison(b, shift, narrow), method)[0] for b in base]
            repair_rows.append({"case": label, "method": method, "brier": brier(y, np.array(preds_v))})
    return pd.DataFrame(stress_rows), pd.DataFrame(repair_rows), base_brier


def grouped_cv_cal_slope(preds: list[PatientPred], comps: dict[str, np.ndarray]) -> pd.DataFrame:
    """Leave-one-centre-out recalibration slope for the main predictors (fixed-param models: only the
    recalibration slope is fit, so only it has apparent-vs-CV optimism)."""
    y = np.array([p.control for p in preds])
    centres = np.array([p.centre for p in preds])
    uniq = sorted(set(centres))
    keys = [k for k in comps if k in ("consensus", "median", "naive_mean_prob") or k.startswith("best_single")]
    rows = []
    for k in keys:
        p = comps[k]
        oof_b = []
        for c in uniq:
            tr, te = centres != c, centres == c
            if te.sum() == 0 or len(np.unique(y[tr])) < 2:
                continue
            b, a = cal_slope_intercept(y[tr], p[tr])  # fit on train centres
            oof_b.append(b)
        rows.append({"predictor": k, "apparent_cal_slope": cal_slope_intercept(y, p)[0],
                     "grouped_cv_cal_slope_mean": float(np.nanmean(oof_b)) if oof_b else math.nan,
                     "n_centres": len(uniq)})
    return pd.DataFrame(rows)


def _git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True)
    args = ap.parse_args()
    root = Path(args.data_root)
    OUT.mkdir(parents=True, exist_ok=True)

    cohort = load_cohort(root)
    preds = per_patient_predictions(cohort)
    y = np.array([p.control for p in preds])
    print(f"HN TCP: analysed n={len(preds)}, controlled={int(y.sum())}, failures={int((1 - y).sum())}")

    wd = weight_distribution(preds)
    wd.to_csv(OUT / "weight_distribution.csv", index=False)
    print("\nB7.3 spontaneous weight distribution:\n" + wd.to_string(index=False))
    # poison the hardest-to-dominate member AMONG models the engine actually combines (sigma>0):
    # if even the lowest-weight participating model captures the consensus when made confident, the
    # pathology is confirmed for this family.
    participating = wd[wd["sigma_median"] > 0]
    poison_model = participating.sort_values("mean_weight_fraction").iloc[0]["model"]

    comps = comparator_predictions(preds)
    app = pd.DataFrame([{"comparator": k, **all_metrics(y, v)} for k, v in comps.items()])
    app.to_csv(OUT / "apparent_metrics.csv", index=False)

    bootstrap_paired(y, comps, ref="consensus").to_csv(OUT / "paired_vs_consensus.csv", index=False)
    # also median vs the field (is the robust combiner non-inferior?)
    bootstrap_paired(y, comps, ref="median").to_csv(OUT / "paired_vs_median.csv", index=False)

    interval_quality(preds).to_csv(OUT / "interval_quality.csv", index=False)
    grouped_cv_cal_slope(preds, comps).to_csv(OUT / "grouped_cv.csv", index=False)

    stress, repairs, base_brier = stress_and_repairs(preds, str(poison_model))
    stress.to_csv(OUT / "stress_test.csv", index=False)
    repairs.to_csv(OUT / "b5_repairs.csv", index=False)
    print("\nB5 repairs:\n" + repairs.to_string(index=False))

    prov = {"analysis": "B7 — TCP-family consensus (HN loco-regional control)", "seed": SEED,
            "n_mc": N_MC, "n_boot": N_BOOT, "n_analysed": len(preds), "controlled": int(y.sum()),
            "failures": int((1 - y).sum()), "models": TCP_MODELS, "poisoned_model": str(poison_model),
            "dvh_reconstruction": "truncnorm(PTV_Dmean, PTV_dose_std), 40 bins",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(), "git_commit": _git_commit(),
            "python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__,
            "stress_clean_consensus_brier": base_brier}
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print("\napparent metrics:\n" + app.to_string(index=False))
    print("wrote ->", OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
