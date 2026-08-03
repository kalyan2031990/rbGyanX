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


def load_cohort(root: Path) -> pd.DataFrame:
    events = pd.read_csv(root / "derived" / "parotid_cohort_full.csv")
    mp = pd.read_csv(root / "derived" / "parotid_pseudonym_map.csv")
    m = events.merge(mp[["pseudonym", "dvh_file"]], on="pseudonym", how="left")
    if m["dvh_file"].isna().any():
        raise SystemExit("pseudonym<->dvh_file mapping incomplete; STOP.")
    return m


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
    args = ap.parse_args()
    root = Path(args.data_root)
    OUT.mkdir(parents=True, exist_ok=True)

    cohort = load_cohort(root)
    preds = per_patient_predictions(root, cohort)
    y = np.array([p.event for p in preds])
    print(f"parotid: analysed n={len(preds)}, events={int(y.sum())}")

    comps = comparator_predictions(preds)
    # apparent metrics per comparator
    app = pd.DataFrame([{"comparator": k, **all_metrics(y, v)} for k, v in comps.items()])
    app.to_csv(OUT / "apparent_metrics.csv", index=False)

    paired = bootstrap_paired(y, comps, ref="consensus")
    paired.to_csv(OUT / "paired_differences.csv", index=False)

    iq = interval_quality(preds)
    iq.to_csv(OUT / "interval_quality.csv", index=False)

    stress, base_m = stress_test(preds)
    stress.to_csv(OUT / "stress_test.csv", index=False)

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
    pd.DataFrame(cal_rows).to_csv(OUT / "calibration_curves.csv", index=False)

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
    (OUT / "provenance.json").write_text(json.dumps(prov, indent=2), encoding="utf-8")
    print("wrote ->", OUT)
    print(app.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
