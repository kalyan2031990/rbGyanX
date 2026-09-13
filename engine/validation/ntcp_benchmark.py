"""
NTCP benchmark path — strictly separate from the TCP path (P1 · S1 + S5).

The "classical" tier here is **the engine's own NTCP model**, evaluated with fixed
literature parameters on the OAR dose. It is never a logistic fitted to the data: a fitted
proxy cannot validate the tool's models, and it silently flatters the classical tier.

Tiers (one leakage-safe protocol, shared with the TCP path via ``four_tier_harness``):
  T1  literature-fixed engine NTCP  (LKB probit | LKB log-logistic | relative seriality)
  T2  MLE refit of the SAME model family (TD50 and steepness re-estimated on the cohort)
  T3  clinical-covariate logistic (EPV-gated)
  T4  dosiomics ML, grouped out-of-fold

Polarity is direct: higher NTCP -> higher probability of the toxicity endpoint. There is no
``1 - TCP`` inversion anywhere in this module; ``extval_benchmark.classical_t1`` is a
**TCP-only** predictor and must never be used here (see ``test_tcp_ntcp_separation``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

SCALAR_MODELS = ("lkb_probit", "lkb_loglogit")
DVH_MODELS = ("rs_poisson",)
NTCP_MODELS = SCALAR_MODELS + DVH_MODELS

_EPS = 1e-6


def classical_ntcp(
    model: str,
    params: dict[str, float],
    *,
    dose_metric: Sequence[float] | None = None,
    dvhs: Sequence[pd.DataFrame] | None = None,
) -> np.ndarray:
    """Fixed-parameter NTCP from the engine's models — one value per patient.

    ``lkb_probit``   : params TD50_gy, m      ; needs ``dose_metric`` (gEUD/mean dose, Gy)
    ``lkb_loglogit`` : params TD50_gy, gamma50; needs ``dose_metric``
    ``rs_poisson``   : params D50_gy, gamma, s; needs ``dvhs`` (differential DVH frames)
    """
    if model not in NTCP_MODELS:
        raise ValueError(f"unknown NTCP model {model!r}; expected one of {NTCP_MODELS}")

    if model in SCALAR_MODELS:
        if dose_metric is None:
            raise ValueError(f"model {model!r} requires dose_metric (gEUD or mean dose, Gy)")
        x = np.asarray(dose_metric, dtype=float)
        if model == "lkb_probit":
            td50, m = float(params["TD50_gy"]), float(params["m"])
            out = [calculate_ntcp_lkb_probit(float(v), td50, m) for v in x]
        else:
            td50, g50 = float(params["TD50_gy"]), float(params["gamma50"])
            out = [calculate_ntcp_lkb_loglogit(float(v), td50, g50) for v in x]
    else:
        if dvhs is None:
            raise ValueError("model 'rs_poisson' requires dvhs (differential DVH frames)")
        d50, gamma, s = float(params["D50_gy"]), float(params["gamma"]), float(params["s"])
        out = [calculate_ntcp_rs_poisson(d, d50, gamma, s) for d in dvhs]

    return np.clip(np.asarray(out, dtype=float), _EPS, 1.0 - _EPS)


def fit_ntcp_mle(
    model: str,
    dose_metric: Sequence[float],
    y: Sequence[int],
    *,
    init: dict[str, float] | None = None,
) -> dict[str, float]:
    """Maximum-likelihood refit of a scalar NTCP model (T2).

    Re-estimates the SAME model family on this cohort (TD50 + steepness), so T2 remains a
    radiobiological dose-response model rather than a generic logistic on dose.
    """
    if model not in SCALAR_MODELS:
        raise ValueError(f"MLE refit supports {SCALAR_MODELS}, got {model!r}")
    x = np.asarray(dose_metric, dtype=float)
    yy = np.asarray(y, dtype=int)
    ok = np.isfinite(x)
    x, yy = x[ok], yy[ok]
    if len(np.unique(yy)) < 2 or len(x) < 3:
        raise ValueError("need both outcome classes and >=3 finite observations to refit")

    med = float(np.median(x)) or 1.0
    p0 = init or (
        {"TD50_gy": med, "m": 0.3} if model == "lkb_probit" else {"TD50_gy": med, "gamma50": 1.5}
    )
    keys = list(p0)

    # A TD50 far outside the observed dose range is not identifiable from these data: with a
    # flat likelihood (no dose-response) an unbounded optimiser wanders to absurd values
    # (TD50 ~ 1e16 Gy) that produce meaningless calibration. Bound to the data-supported range
    # and to physically plausible steepness, then report whether the fit is usable.
    d_lo, d_hi = float(np.min(x)), float(np.max(x))
    td50_bounds = (max(1.0, 0.5 * d_lo), min(200.0, max(2.0 * d_hi, d_hi + 10.0)))
    steep_bounds = (0.02, 1.5) if model == "lkb_probit" else (0.1, 10.0)

    def nll(theta: np.ndarray) -> float:
        td50, steep = float(theta[0]), float(theta[1])
        if td50 <= 0 or steep <= 0:
            return 1e12
        pr = classical_ntcp(model, {keys[0]: td50, keys[1]: steep}, dose_metric=x)
        pr = np.clip(pr, _EPS, 1 - _EPS)
        return float(-np.sum(yy * np.log(pr) + (1 - yy) * np.log(1 - pr)))

    x0 = np.array(
        [
            float(np.clip(p0[keys[0]], *td50_bounds)),
            float(np.clip(p0[keys[1]], *steep_bounds)),
        ]
    )
    res = minimize(nll, x0=x0, method="L-BFGS-B", bounds=[td50_bounds, steep_bounds])

    td50_fit, steep_fit = float(res.x[0]), float(res.x[1])
    # "Plausible" = the optimiser settled inside the admissible region rather than being pinned
    # to a bound, and TD50 sits within the observed dose span (i.e. the data can identify it).
    at_bound = (
        abs(td50_fit - td50_bounds[0]) < 1e-6
        or abs(td50_fit - td50_bounds[1]) < 1e-6
        or abs(steep_fit - steep_bounds[0]) < 1e-9
        or abs(steep_fit - steep_bounds[1]) < 1e-9
    )
    identifiable = d_lo <= td50_fit <= d_hi
    return {
        keys[0]: td50_fit,
        keys[1]: steep_fit,
        "converged": bool(res.success),
        "plausible": bool(res.success and not at_bound and identifiable),
        "td50_bounds": td50_bounds,
    }


def run_ntcp_benchmark(
    df: pd.DataFrame,
    *,
    endpoint: str,
    model: str,
    params: dict[str, float],
    dose_metric_col: str | None = None,
    dvhs: Sequence[pd.DataFrame] | None = None,
    covariate_cols: Sequence[str] | None = None,
    dosiomics_cols: Sequence[str] | None = None,
    groups_col: str | None = None,
    n_splits: int = 5,
    seed: int = 0,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Run the four NTCP tiers. T1/T2 are engine NTCP models — never a fitted proxy."""
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedGroupKFold

    from validation.extval_benchmark import net_benefit
    from validation.four_tier_harness import run_four_tier_harness

    work = df[df[endpoint].notna()].reset_index(drop=True)

    # A patient whose OAR dose is missing has no computable NTCP. Exclude them explicitly and
    # report the count — never impute to 0.0 (that would fabricate a "no complication" patient
    # and bias the classical tier). Mirrors the engine's NaN-not-zero contract.
    dose_all = work[dose_metric_col].to_numpy(dtype=float) if dose_metric_col else None
    p_all = classical_ntcp(model, params, dose_metric=dose_all, dvhs=dvhs)
    keep = np.isfinite(p_all)
    n_excluded = int((~keep).sum())
    if n_excluded:
        work = work.loc[keep].reset_index(drop=True)
        if dvhs is not None:
            dvhs = [d for d, k in zip(dvhs, keep, strict=False) if k]
        p_all = p_all[keep]
        dose_all = dose_all[keep] if dose_all is not None else None

    y = work[endpoint].astype(int).to_numpy()
    groups = (
        work[groups_col].astype(str).to_numpy()
        if groups_col
        else np.asarray([str(i) for i in range(len(work))])
    )
    dose = dose_all
    p_t1 = p_all

    if len(np.unique(y)) < 2:
        raise ValueError(
            f"endpoint {endpoint!r} has a single class after excluding "
            f"{n_excluded} patient(s) with missing OAR dose"
        )

    # T2: refit the same family (scalar models only).
    p_t2 = None
    refit: dict[str, float] | None = None
    if model in SCALAR_MODELS and dose is not None:
        try:
            refit = fit_ntcp_mle(model, dose, y)
            _META = ("converged", "plausible", "td50_bounds")
            fitted = {k: v for k, v in refit.items() if k not in _META}
            p_t2 = classical_ntcp(model, fitted, dose_metric=dose)
        except ValueError:
            p_t2 = None

    # T4: grouped out-of-fold dosiomics ML.
    p_ml = None
    if dosiomics_cols:
        X = np.nan_to_num(work[list(dosiomics_cols)].to_numpy(dtype=float), nan=0.0)
        oof = np.full(len(y), np.nan)
        k = int(min(n_splits, len(np.unique(groups)), min(int(y.sum()), int((y == 0).sum()))))
        if k >= 2:
            skf = StratifiedGroupKFold(n_splits=k, shuffle=True, random_state=seed)
            for tr, te in skf.split(X, y, groups):
                if len(np.unique(y[tr])) < 2:
                    continue
                rf = RandomForestClassifier(
                    n_estimators=300, max_depth=3, min_samples_leaf=5, random_state=seed, n_jobs=1
                )
                rf.fit(X[tr], y[tr])
                oof[te] = rf.predict_proba(X[te])[:, 1]
        p_ml = np.nan_to_num(oof, nan=float(y.mean()))

    cov = work[list(covariate_cols)] if covariate_cols else None
    res = run_four_tier_harness(
        y_true=y,
        classical_probs=p_t1,
        patient_ids=groups,
        clinical_features=cov,
        ml_probs=p_ml,
        mle_probs=p_t2,
        n_splits=n_splits,
    )

    dca = {"T1": p_t1, "T2": p_t2, "T4": p_ml}
    rows = []
    for key in ("T1", "T2", "T3", "T4"):
        tr = res.get(key)
        if tr is None:
            continue
        pr = dca.get(key)
        rows.append(
            {
                "tier": tr.tier,
                "model": tr.model_name if key != "T1" else f"engine_{model}",
                "n": int(len(y)),
                "events": int(y.sum()),
                "apparent_auc": round(tr.apparent_auc, 3),
                "cv_auc": round(tr.cv_auc, 3),
                "optimism": round(tr.apparent_auc - tr.cv_auc, 3),
                "brier": round(tr.brier, 3),
                "ece": round(tr.ece, 3),
                "cal_slope": round(tr.calibration_slope, 3),
                "net_benefit": round(net_benefit(y, pr), 4) if pr is not None else float("nan"),
                "epv": round(tr.epv, 1) if tr.epv is not None else None,
                "refused": tr.refused,
                "note": (
                    "refit not identifiable from these data (flat likelihood)"
                    if key == "T2" and refit is not None and not refit.get("plausible", False)
                    else tr.refusal_reason
                ),
            }
        )

    extras: dict[str, Any] = {
        "n": int(len(y)),
        "events": int(y.sum()),
        "n_excluded_missing_dose": n_excluded,
        "model": model,
        "fixed_params": dict(params),
        "refit_params": refit,
        "endpoint": endpoint,
        "seed": seed,
        "classical_is_engine_model": True,
    }
    return pd.DataFrame(rows), extras
