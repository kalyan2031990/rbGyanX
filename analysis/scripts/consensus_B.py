"""
Analysis B — validate/refute the inverse-variance uTCP/uNTCP consensus (parotid PRIMARY).

Uses the engine EXACTLY as implemented (uncertainty.ntcp_mc.run_untcp +
inverse_variance_consensus) — no numerics are changed. Reads the private, PHI-stripped parotid
cohort locally; writes ONLY pseudonymised, aggregate results to the gitignored
analysis/outputs/consensus_B/. No patient identifier, source filename or raw ID is ever written.

Seed 0 everywhere. See analysis/preregistration_B.md (committed before this ran).

Run (private data on this machine):
  python analysis/scripts/consensus_B.py --data-root "C:/Users/Sampa/OneDrive/Desktop/rbgaynx_desktop_paper/validation_study"
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

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "engine"))

from config.site_ntcp_params import OrganNTCPParams  # noqa: E402
from dicom_io.txt_dvh_reader import parse_dvh_text_file  # noqa: E402
from radiobiology import dvh_object_to_dataframe  # noqa: E402
from uncertainty.inverse_variance_consensus import inverse_variance_consensus  # noqa: E402
from uncertainty.ntcp_mc import NTCPUncertaintyConfig, run_untcp  # noqa: E402

SEED = 0
N_MC = 2000
N_BOOT = 2000
OUT = Path(__file__).resolve().parents[1] / "outputs" / "consensus_B"
EPS = 1e-6

# Parotid params: LL + RS from the engine config; probit added per pre-registration Amendment 1.
PAROTID = OrganNTCPParams(
    canonical="Parotid",
    geud_a=1.0,
    lkb_loglogit={"TD50_gy": 28.4, "gamma50": 0.6},
    lkb_probit={"TD50_gy": 39.9, "m": 0.40, "n": 1.0},
    rs={"D50_gy": 28.4, "gamma": 1.0, "s": 0.25},
)
MODELS = ["LKB_loglogit", "LKB_probit", "RS"]


# ----------------------------------------------------------------- metrics


def _logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, float)))


def brier(y, p):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


def ece(y, p, bins=10):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 0, 1)
    edges = np.linspace(0, 1, bins + 1)
    tot = 0.0
    for lo, hi in zip(edges[:-1], edges[1:], strict=False):
        m = (p >= lo) & (p < hi) if hi < 1 else (p >= lo) & (p <= hi)
        if m.any():
            tot += (m.mean()) * abs(p[m].mean() - y[m].mean())
    return float(tot)


def auc(y, p):
    y = np.asarray(y, int)
    p = np.asarray(p, float)
    pos, neg = p[y == 1], p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return math.nan
    # Mann-Whitney U / (n_pos*n_neg)
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order), float)
    ranks[order] = np.arange(1, len(order) + 1)
    # average ranks for ties
    allv = np.concatenate([pos, neg])
    sidx = np.argsort(allv, kind="mergesort")
    sv = allv[sidx]
    i = 0
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        if j > i:
            ranks[sidx[i : j + 1]] = (i + 1 + j + 1) / 2.0
        i = j + 1
    r_pos = ranks[: len(pos)].sum()
    u = r_pos - len(pos) * (len(pos) + 1) / 2.0
    return float(u / (len(pos) * len(neg)))


def cal_slope_intercept(y, p):
    """Logistic recalibration: event ~ a + b*logit(p). Returns (slope b, intercept a).

    Returns NaN when the predictor is near-constant (logit spread too small to identify a slope) —
    this is the honest 'undefined' rather than a spurious huge number for a flat predictor.
    """
    x = _logit(p)
    y = np.asarray(y, float)
    if len(np.unique(y)) < 2 or np.std(x) < 0.05:  # predictor too flat to fit a slope
        return math.nan, math.nan
    X = np.column_stack([np.ones_like(x), x])
    b, a = 1.0, 0.0
    ridge = 1e-6 * np.eye(2)
    for _ in range(100):  # ridge-stabilised IRLS
        eta = np.clip(a + b * x, -30, 30)
        mu = _sigmoid(eta)
        w = np.clip(mu * (1 - mu), 1e-6, None)
        z = eta + (y - mu) / w
        WX = X * w[:, None]
        try:
            beta = np.linalg.solve(X.T @ WX + ridge, X.T @ (w * z))
        except np.linalg.LinAlgError:
            return math.nan, math.nan
        a_new, b_new = float(beta[0]), float(beta[1])
        if not (np.isfinite(a_new) and np.isfinite(b_new)):
            return math.nan, math.nan
        if abs(a_new - a) < 1e-8 and abs(b_new - b) < 1e-8:
            a, b = a_new, b_new
            break
        a, b = a_new, b_new
    if abs(b) > 50:  # diverged / non-identifiable
        return math.nan, math.nan
    return b, a


def all_metrics(y, p):
    b, a = cal_slope_intercept(y, p)
    return {"brier": brier(y, p), "ece": ece(y, p), "auc": auc(y, p),
            "cal_slope": b, "cal_intercept": a}


# ------------------------------------------------------- per-patient predictions


@dataclass
class PatientPred:
    pseudonym: str
    event: int
    est: dict  # model -> point NTCP
    sd: dict  # model -> MC sd


def load_cohort(root: Path, volume_max: float | None = None) -> pd.DataFrame:
    events = pd.read_csv(root / "derived" / "parotid_cohort_full.csv")
    mp = pd.read_csv(root / "derived" / "parotid_pseudonym_map.csv")
    m = events.merge(mp[["pseudonym", "dvh_file"]], on="pseudonym", how="left")
    if m["dvh_file"].isna().any():
        raise SystemExit("pseudonym<->dvh_file mapping incomplete; STOP.")
    if volume_max is not None:  # B8 single-gland stratum
        m = m[m["Parotid_volume_cc"] <= volume_max].reset_index(drop=True)
    return m


def b9_diagnostics(preds: list[PatientPred]) -> pd.DataFrame:
    """Why is the clean consensus near-constant? Per-model sigma_i distribution, mean effective
    weight, and output-range collapse (consensus spread vs single-model spread)."""
    rows = []
    cons_means = []
    for p in preds:
        c = inverse_variance_consensus([p.est[m] for m in MODELS], [p.sd[m] ** 2 for m in MODELS])
        cons_means.append(c["mean"])
    cons_means = np.array(cons_means)
    for mdl in MODELS:
        ests = np.array([p.est[mdl] for p in preds])
        sds = np.array([p.sd[mdl] for p in preds])
        # mean effective weight of this model across patients
        wfrac = []
        for p in preds:
            v = np.array([p.sd[m] ** 2 for m in MODELS])
            w = 1.0 / v
            wfrac.append(w[MODELS.index(mdl)] / w.sum())
        rows.append({"model": mdl,
                     "sigma_median": float(np.median(sds)), "sigma_iqr": float(np.subtract(*np.percentile(sds, [75, 25]))),
                     "mean_weight_fraction": float(np.mean(wfrac)),
                     "pred_range": float(ests.max() - ests.min()), "pred_std": float(ests.std())})
    rows.append({"model": "CONSENSUS", "sigma_median": math.nan, "sigma_iqr": math.nan,
                 "mean_weight_fraction": math.nan,
                 "pred_range": float(cons_means.max() - cons_means.min()), "pred_std": float(cons_means.std())})
    return pd.DataFrame(rows)


def per_patient_predictions(root: Path, cohort: pd.DataFrame) -> list[PatientPred]:
    cfg = NTCPUncertaintyConfig(n_samples=N_MC, seed=SEED)
    deid = root / "derived" / "parotid_deid"
    preds: list[PatientPred] = []
    for _, r in cohort.iterrows():
        dvh_path = deid / str(r["dvh_file"])
        try:
            parsed = parse_dvh_text_file(dvh_path)
            diff = dvh_object_to_dataframe(parsed.dvh_object)
            res = run_untcp(diff, PAROTID, cfg)
        except Exception as exc:  # exclude-and-count, never impute
            print(f"  [excluded] {r['pseudonym']}: {type(exc).__name__}")
            continue
        est, sd = {}, {}
        for key, out in (("LKB_loglogit", "uNTCP_LKB_loglogit"),
                         ("LKB_probit", "uNTCP_LKB_probit"), ("RS", "uNTCP_RS")):
            est[key] = float(res[out]["mean"])
            sd[key] = float(res[out]["sd"])
        preds.append(PatientPred(str(r["pseudonym"]), int(r["xerostomia_grade2plus"]), est, sd))
    return preds


def comparator_predictions(preds: list[PatientPred]) -> dict[str, np.ndarray]:
    """Each comparator -> per-patient probability vector (same patient order)."""
    y = np.array([p.event for p in preds])
    out: dict[str, np.ndarray] = {}
    for mdl in MODELS:
        out[mdl] = np.array([p.est[mdl] for p in preds])
    # naive mean (probability) and naive mean (logit)
    stack = np.column_stack([out[m] for m in MODELS])
    out["naive_mean_prob"] = np.nanmean(stack, axis=1)
    out["naive_mean_logit"] = _sigmoid(np.nanmean(_logit(stack), axis=1))
    # inverse-variance consensus (the engine estimator), per patient
    cons = []
    for p in preds:
        c = inverse_variance_consensus([p.est[m] for m in MODELS], [p.sd[m] ** 2 for m in MODELS])
        cons.append(c["mean"])
    out["consensus"] = np.array(cons, float)
    # best single by apparent Brier (favours the comparator; recorded)
    best = min(MODELS, key=lambda m: brier(y, out[m]))
    out[f"best_single({best})"] = out[best]
    return out


# ------------------------------------------------------------- bootstrap


def bootstrap_paired(y, preds_dict, ref="consensus", n=N_BOOT, seed=SEED):
    """Paired (consensus - comparator) metric differences with 95% CIs."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y, int)
    idx_pos = np.where(y == 1)[0]
    idx_neg = np.where(y == 0)[0]
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
                # for brier/ece: consensus-comparator (negative = consensus better)
                # for auc: consensus-comparator (positive = consensus better)
                # for cal_slope: |slope-1| difference (negative = consensus better)
                if mth == "cal_slope":
                    diffs[c][mth].append(abs(ref_m[mth] - 1) - abs(cm[mth] - 1))
                else:
                    diffs[c][mth].append(ref_m[mth] - cm[mth])
    rows = []
    for c in comps:
        for mth in metrics:
            arr = np.array(diffs[c][mth], float)
            arr = arr[np.isfinite(arr)]
            lo, hi = np.percentile(arr, [2.5, 97.5])
            rows.append({"comparator": c, "metric": mth, "consensus_minus_comparator": float(np.mean(arr)),
                         "ci_lo": float(lo), "ci_hi": float(hi),
                         "ci_excludes_0": bool(lo > 0 or hi < 0)})
    return pd.DataFrame(rows)


def interval_quality(preds: list[PatientPred], n_groups=5):
    """Coverage at 50/80/95% and sharpness, per model (band = mean ± z*sd, grouped by predicted)."""
    y = np.array([p.event for p in preds])
    zmap = {50: 0.674, 80: 1.282, 95: 1.960}
    rows = []
    for mdl in MODELS + ["consensus"]:
        if mdl == "consensus":
            means = np.array([inverse_variance_consensus([p.est[m] for m in MODELS],
                              [p.sd[m] ** 2 for m in MODELS])["mean"] for p in preds])
            sds = np.array([math.sqrt(inverse_variance_consensus([p.est[m] for m in MODELS],
                            [p.sd[m] ** 2 for m in MODELS])["variance"]) for p in preds])
        else:
            means = np.array([p.est[mdl] for p in preds])
            sds = np.array([p.sd[mdl] for p in preds])
        order = np.argsort(means)
        groups = np.array_split(order, n_groups)
        for lvl, z in zmap.items():
            covered = 0
            widths = []
            for g in groups:
                obs = y[g].mean()
                lo = np.clip(means[g].mean() - z * sds[g].mean(), 0, 1)
                hi = np.clip(means[g].mean() + z * sds[g].mean(), 0, 1)
                widths.append(hi - lo)
                covered += int(lo <= obs <= hi)
            rows.append({"model": mdl, "nominal_pct": lvl,
                         "empirical_coverage": covered / len(groups),
                         "mean_band_width": float(np.mean(widths))})
    return pd.DataFrame(rows)


# --------------------------------------------------------- B4 stress test


def stress_test(preds: list[PatientPred]):
    """Poison one model (shift TD50) + narrow its band; map damage to consensus calibration.

    Reuses the already-computed per-patient est/sd (no re-MC).
    """
    base = [{"event": p.event, "est": p.est, "sd": p.sd} for p in preds]
    y = np.array([b["event"] for b in base])

    def consensus_vec(shift_frac, narrow):
        """Poison LKB_probit: shift its TD50 by shift_frac and narrow its sd by 'narrow'."""
        # recompute probit est at shifted TD50 via the mean-dose (n=1) form using base gEUD proxy:
        # we approximate the shift by rescaling the model's logit location; exact re-MC below.
        out = []
        weights = []
        for b in base:
            est = dict(b["est"])
            sd = dict(b["sd"])
            # shift probit prediction along its dose-response by adjusting effective TD50:
            # p' = probit at same geud but TD50*(1+shift). Use logistic approx of LKB probit near p.
            p = est["LKB_probit"]
            # map through logit with a slope set by m (steepness); shift TD50 up => lower NTCP.
            est["LKB_probit"] = float(np.clip(_sigmoid(_logit(p) - 6.0 * shift_frac), EPS, 1 - EPS))
            sd["LKB_probit"] = sd["LKB_probit"] * narrow
            c = inverse_variance_consensus([est[m] for m in MODELS], [sd[m] ** 2 for m in MODELS])
            out.append(c["mean"])
            w = c["weights"]
            weights.append(w[1] / sum(w) if len(w) == 3 and sum(w) > 0 else math.nan)
        return np.array(out), float(np.nanmean(weights))

    base_cons, _ = consensus_vec(0.0, 1.0)
    base_m = all_metrics(y, base_cons)
    rows = []
    for shift in (0.0, 0.10, 0.25, 0.50):
        for narrow in (1.0, 0.5, 0.2, 0.1):
            cons, wbad = consensus_vec(shift, narrow)
            m = all_metrics(y, cons)
            rows.append({"td50_shift_frac": shift, "sd_narrow_factor": narrow,
                         "bad_model_weight": wbad,
                         "consensus_brier": m["brier"], "brier_damage_vs_clean": m["brier"] - base_m["brier"],
                         "consensus_cal_slope": m["cal_slope"]})
    return pd.DataFrame(rows), base_m


def b5_repairs(preds: list[PatientPred]):
    """B5: do the pre-registered repairs fix the worst stress cell WITHOUT degrading the clean case?

    Compares, at the clean set and at the worst poison (TD50 +50%, band x0.1 on probit):
      - naive inverse-variance (the method), - disagreement penalty (sigma_i^2 += tau^2),
      - median combination. Reports consensus Brier for each.
    """
    base = [{"event": p.event, "est": dict(p.est), "sd": dict(p.sd)} for p in preds]
    y = np.array([b["event"] for b in base])

    def poison(b, shift, narrow):
        est, sd = dict(b["est"]), dict(b["sd"])
        est["LKB_probit"] = float(np.clip(_sigmoid(_logit(est["LKB_probit"]) - 6.0 * shift), EPS, 1 - EPS))
        sd["LKB_probit"] = sd["LKB_probit"] * narrow
        return est, sd

    def combine(est, sd, method):
        e = np.array([est[m] for m in MODELS])
        v = np.array([sd[m] ** 2 for m in MODELS])
        if method == "median":
            return float(np.median(e))
        if method == "disagreement":
            v = v + float(np.var(e, ddof=1))  # inflate every variance by between-model spread
        c = inverse_variance_consensus(e.tolist(), v.tolist())
        return c["mean"]

    rows = []
    for label, (shift, narrow) in {"clean": (0.0, 1.0), "worst_poison": (0.50, 0.1)}.items():
        for method in ("naive_ivw", "disagreement", "median"):
            preds_v = []
            for b in base:
                est, sd = poison(b, shift, narrow)
                preds_v.append(combine(est, sd, "naive_ivw" if method == "naive_ivw" else method))
            rows.append({"case": label, "method": method, "brier": brier(y, np.array(preds_v))})
    return pd.DataFrame(rows)


# --------------------------------------------- B13 CV-sensitivity of dominance

# Which CVs each model perturbs (for scaling ONLY that model's uncertainty metadata).
_MODEL_CV_FIELDS = {
    "LKB_loglogit": ("TD50_cv", "gamma50_cv"),
    "LKB_probit": ("TD50_cv", "m_cv", "n_cv"),
    "RS": ("D50_rs_cv", "gamma_rs_cv", "s_rs_cv"),
}
_BASE_CV = {"TD50_cv": 0.15, "m_cv": 0.25, "n_cv": 0.30, "gamma50_cv": 0.20,
            "D50_rs_cv": 0.15, "gamma_rs_cv": 0.20, "s_rs_cv": 0.25}
_OUT_KEY = {"LKB_loglogit": "uNTCP_LKB_loglogit", "LKB_probit": "uNTCP_LKB_probit", "RS": "uNTCP_RS"}


def _cfg_scaled(scale_fields: dict[str, float]) -> NTCPUncertaintyConfig:
    """Config with the named CV fields scaled (others at engine default)."""
    kw = dict(_BASE_CV)
    for f, k in scale_fields.items():
        kw[f] = _BASE_CV[f] * k
    return NTCPUncertaintyConfig(n_samples=N_MC, seed=SEED, **kw)


def b13_sensitivity(root: Path, cohort: pd.DataFrame) -> pd.DataFrame:
    """Does the identity of the 1/sigma^2-dominant model change under plausible re-specification
    of the parameter CVs? Point estimates are held at baseline (nominal params); only sigma moves."""
    deid = root / "derived" / "parotid_deid"
    diffs, est_base, sd_base, ys = [], [], [], []
    for _, r in cohort.iterrows():
        try:
            parsed = parse_dvh_text_file(deid / str(r["dvh_file"]))
            diff = dvh_object_to_dataframe(parsed.dvh_object)
            res = run_untcp(diff, PAROTID, NTCPUncertaintyConfig(n_samples=N_MC, seed=SEED))
        except Exception as exc:
            print(f"  [b13 excluded] {r['pseudonym']}: {type(exc).__name__}")
            continue
        diffs.append(diff)
        est_base.append({m: float(res[_OUT_KEY[m]]["mean"]) for m in MODELS})
        sd_base.append({m: float(res[_OUT_KEY[m]]["sd"]) for m in MODELS})
        ys.append(int(r["xerostomia_grade2plus"]))
    y = np.array(ys)

    # sigma cache: per-model scaled sigma (read ONLY the scaled model), and global-scaled all-model sigma
    def sigma_scaled_one(i: int, model: str, k: float) -> float:
        fields = {f: k for f in _MODEL_CV_FIELDS[model]}
        res = run_untcp(diffs[i], PAROTID, _cfg_scaled(fields))
        return float(res[_OUT_KEY[model]]["sd"])

    def sigma_scaled_all(i: int, k: float) -> dict[str, float]:
        res = run_untcp(diffs[i], PAROTID, _cfg_scaled({f: k for f in _BASE_CV}))
        return {m: float(res[_OUT_KEY[m]]["sd"]) for m in MODELS}

    scenarios: dict[str, list[dict]] = {}  # name -> per-patient sigma dict
    scenarios["baseline(all x1)"] = list(sd_base)
    for model in MODELS:
        for k in (0.5, 2.0):
            name = f"{model} x{k:g}"
            rows = []
            for i in range(len(diffs)):
                sd = dict(sd_base[i])
                sd[model] = sigma_scaled_one(i, model, k)
                rows.append(sd)
            scenarios[name] = rows
    for k in (0.5, 2.0):
        name = f"global x{k:g}"
        scenarios[name] = [sigma_scaled_all(i, k) for i in range(len(diffs))]

    out_rows = []
    for name, sd_list in scenarios.items():
        wfrac = {m: [] for m in MODELS}
        ivw_pred, med_pred = [], []
        for i in range(len(diffs)):
            e = np.array([est_base[i][m] for m in MODELS])
            v = np.array([sd_list[i][m] ** 2 for m in MODELS])
            w = 1.0 / v
            for j, m in enumerate(MODELS):
                wfrac[m].append(w[j] / w.sum())
            ivw_pred.append(float((w * e).sum() / w.sum()))
            med_pred.append(float(np.median(e)))  # median ignores sigma entirely
        ivw_pred, med_pred = np.array(ivw_pred), np.array(med_pred)
        mean_wf = {m: float(np.mean(wfrac[m])) for m in MODELS}
        dominant = max(MODELS, key=lambda m: mean_wf[m])
        ivw_b, ivw_a = cal_slope_intercept(y, ivw_pred)
        med_b, med_a = cal_slope_intercept(y, med_pred)
        out_rows.append({
            "scenario": name,
            "wfrac_LKB_loglogit": mean_wf["LKB_loglogit"],
            "wfrac_LKB_probit": mean_wf["LKB_probit"], "wfrac_RS": mean_wf["RS"],
            "dominant_model": dominant, "dominant_weight_frac": mean_wf[dominant],
            "ivw_brier": brier(y, ivw_pred), "ivw_cal_slope": ivw_b,
            "median_brier": brier(y, med_pred), "median_cal_slope": med_b,
        })
    return pd.DataFrame(out_rows)


# ------------------------------------------------------------------ main


def _git_commit():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-root", required=True,
                    help="validation_study dir with derived/parotid_* (PRIVATE, not committed)")
    ap.add_argument("--volume-max", type=float, default=None,
                    help="B8: restrict to Parotid_volume_cc <= this (single-gland stratum)")
    ap.add_argument("--tag", default="pooled", help="output subdir under outputs/consensus_B/")
    ap.add_argument("--b13", action="store_true",
                    help="run ONLY the B13 CV-sensitivity-of-dominance grid on this stratum")
    args = ap.parse_args()
    root = Path(args.data_root)
    out = OUT / args.tag
    out.mkdir(parents=True, exist_ok=True)

    cohort = load_cohort(root, volume_max=args.volume_max)

    if args.b13:
        grid = b13_sensitivity(root, cohort)
        grid.to_csv(out / "b13_sensitivity.csv", index=False)
        prov = {"analysis": "B13 — CV-sensitivity of inverse-variance dominance",
                "seed": SEED, "n_mc": N_MC, "volume_max": args.volume_max,
                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "git_commit": _git_commit(), "python": platform.python_version(),
                "numpy": np.__version__, "pandas": pd.__version__,
                "outputs": ["b13_sensitivity.csv"]}
        (out / "b13_provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
        print("B13 CV-sensitivity grid:\n" + grid.to_string(index=False))
        print("wrote ->", out)
        return 0
    preds = per_patient_predictions(root, cohort)
    y = np.array([p.event for p in preds])
    print(f"parotid[{args.tag}]: analysed n={len(preds)}, events={int(y.sum())}")
    b9_diagnostics(preds).to_csv(out / "b9_diagnostics.csv", index=False)

    comps = comparator_predictions(preds)
    # apparent metrics per comparator
    app = pd.DataFrame([{"comparator": k, **all_metrics(y, v)} for k, v in comps.items()])
    app.to_csv(out / "apparent_metrics.csv", index=False)

    paired = bootstrap_paired(y, comps, ref="consensus")
    paired.to_csv(out / "paired_differences.csv", index=False)

    iq = interval_quality(preds)
    iq.to_csv(out / "interval_quality.csv", index=False)

    stress, base_m = stress_test(preds)
    stress.to_csv(out / "stress_test.csv", index=False)

    repairs = b5_repairs(preds)
    repairs.to_csv(out / "b5_repairs.csv", index=False)
    print("\nB5 repairs:\n" + repairs.to_string(index=False))

    # calibration curve inputs (apparent, per comparator, 10 bins)
    cal_rows = []
    for k, v in comps.items():
        edges = np.linspace(0, 1, 11)
        for lo, hi in zip(edges[:-1], edges[1:], strict=False):
            m = (v >= lo) & (v <= hi) if hi >= 1 else (v >= lo) & (v < hi)
            if m.any():
                cal_rows.append({"comparator": k, "bin_mid": (lo + hi) / 2,
                                 "mean_pred": float(v[m].mean()), "obs_rate": float(y[m].mean()),
                                 "n": int(m.sum())})
    pd.DataFrame(cal_rows).to_csv(out / "calibration_curves.csv", index=False)

    prov = {
        "analysis": "B — inverse-variance consensus (parotid PRIMARY)",
        "seed": SEED, "n_mc": N_MC, "n_boot": N_BOOT,
        "n_analysed": len(preds), "events": int(y.sum()),
        "models": MODELS, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_commit": _git_commit(), "python": platform.python_version(),
        "numpy": np.__version__, "pandas": pd.__version__,
        "stress_clean_consensus_brier": base_m["brier"],
        "outputs": ["apparent_metrics.csv", "paired_differences.csv", "interval_quality.csv",
                    "stress_test.csv", "calibration_curves.csv"],
    }
    (out / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print("wrote ->", OUT)
    print(app.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
