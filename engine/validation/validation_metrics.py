"""Publication-standard NTCP/TCP validation metrics (AUC, calibration, H-L, ECE, Brier)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    model_name: str
    n_patients: int
    n_events: int
    auc: float = math.nan
    auc_ci_lower: float = math.nan
    auc_ci_upper: float = math.nan
    brier_score: float = math.nan
    brier_ci_lower: float = math.nan
    brier_ci_upper: float = math.nan
    cal_slope: float = math.nan
    cal_intercept: float = math.nan
    hl_stat: float = math.nan
    hl_p_value: float = math.nan
    ece: float = math.nan
    calibration_df: pd.DataFrame = field(default_factory=pd.DataFrame)


def compute_auc(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    from sklearn.metrics import roc_auc_score

    y_true = np.asarray(y_true, dtype=float)
    if len(np.unique(y_true)) < 2:
        return math.nan
    try:
        return float(roc_auc_score(y_true, y_pred))
    except Exception:
        return math.nan


def compute_brier(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    return float(np.mean((y_pred - y_true) ** 2))


def hosmer_lemeshow(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    n_groups: int = 10,
) -> tuple[float, float, pd.DataFrame]:
    from scipy.stats import chi2

    df = pd.DataFrame({"obs": y_true, "pred": y_pred})
    df["decile"] = pd.qcut(df["pred"], q=n_groups, labels=False, duplicates="drop")
    rows = []
    hl_stat = 0.0
    for g, grp in df.groupby("decile"):
        obs = grp["obs"].sum()
        pred = grp["pred"].sum()
        n = len(grp)
        if pred > 0 and (n - pred) > 0:
            hl_stat += (obs - pred) ** 2 / (pred * (1 - pred / n))
        rows.append(
            {
                "decile": g,
                "n": n,
                "observed_events": obs,
                "predicted_events": round(pred, 2),
                "observed_rate": round(obs / n, 4) if n > 0 else math.nan,
                "predicted_mean": round(grp["pred"].mean(), 4),
            }
        )
    p_val = float(1 - chi2.cdf(hl_stat, df=max(n_groups - 2, 1)))
    return float(hl_stat), p_val, pd.DataFrame(rows)


def calibration_slope(y_true: np.ndarray, y_pred: np.ndarray) -> tuple[float, float]:
    from scipy.special import logit
    from scipy.optimize import minimize

    p = np.clip(y_pred, 1e-6, 1 - 1e-6)
    lp = logit(p)

    def neg_ll(params):
        intercept, slope = params
        log_odds = intercept + slope * lp
        prob = 1 / (1 + np.exp(-log_odds))
        prob = np.clip(prob, 1e-9, 1 - 1e-9)
        return -np.sum(y_true * np.log(prob) + (1 - y_true) * np.log(1 - prob))

    res = minimize(neg_ll, x0=[0.0, 1.0], method="Nelder-Mead")
    if res.success:
        return float(res.x[1]), float(res.x[0])
    return math.nan, math.nan


def expected_calibration_error(
    y_true: np.ndarray, y_pred: np.ndarray, n_bins: int = 10
) -> float:
    bins = np.linspace(0, 1, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        mask = (y_pred >= bins[i]) & (y_pred < bins[i + 1])
        if mask.sum() == 0:
            continue
        ece += (mask.sum() / n) * abs(y_true[mask].mean() - y_pred[mask].mean())
    return float(ece)


def bootstrap_ci(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    metric_fn: Callable,
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    scores = []
    n = len(y_true)
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        val = metric_fn(y_true[idx], y_pred[idx])
        if not math.isnan(val):
            scores.append(val)
    if len(scores) < 10:
        return math.nan, math.nan
    alpha = (1 - ci) / 2
    return float(np.percentile(scores, alpha * 100)), float(
        np.percentile(scores, (1 - alpha) * 100)
    )


def validate_ntcp_model(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    model_name: str = "LKB",
    n_bootstrap: int = 500,
) -> ValidationResult:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    valid = np.isfinite(y_true) & np.isfinite(y_pred)
    y_true, y_pred = y_true[valid], y_pred[valid]
    n = len(y_true)
    n_events = int(y_true.sum())
    if n < 10 or n_events < 5:
        logger.warning(
            "validate_ntcp_model: n=%d events=%d — metrics may be unreliable.",
            n,
            n_events,
        )
    auc = compute_auc(y_true, y_pred)
    brier = compute_brier(y_true, y_pred)
    hl_stat, hl_p, cal_df = hosmer_lemeshow(y_true, y_pred)
    slope, intercept = calibration_slope(y_true, y_pred)
    ece = expected_calibration_error(y_true, y_pred)
    auc_lo, auc_hi = (math.nan, math.nan)
    brier_lo, brier_hi = (math.nan, math.nan)
    if n_bootstrap > 0 and n >= 10:
        auc_lo, auc_hi = bootstrap_ci(y_true, y_pred, compute_auc, n_bootstrap)
        brier_lo, brier_hi = bootstrap_ci(y_true, y_pred, compute_brier, n_bootstrap)
    return ValidationResult(
        model_name=model_name,
        n_patients=n,
        n_events=n_events,
        auc=auc,
        auc_ci_lower=auc_lo,
        auc_ci_upper=auc_hi,
        brier_score=brier,
        brier_ci_lower=brier_lo,
        brier_ci_upper=brier_hi,
        cal_slope=slope,
        cal_intercept=intercept,
        hl_stat=hl_stat,
        hl_p_value=hl_p,
        ece=ece,
        calibration_df=cal_df,
    )


def validation_result_to_dict(vr: ValidationResult) -> dict:
    """
    Publication-ready dict with all discrimination and calibration metrics.

    Keys added by CURSOR_FINAL_FIXES FIX-6:
      Brier_95CI   -- bootstrap 95 % CI on Brier score
      cal_adequate -- True when Hosmer-Lemeshow p > 0.05 (adequate calibration)
    """
    def _fmt_ci(lo: float, hi: float) -> str:
        if math.isfinite(lo) and math.isfinite(hi):
            return f"[{lo:.3f}, {hi:.3f}]"
        return "n/a"

    hl_p = vr.hl_p_value
    return {
        "model":         vr.model_name,
        "n_patients":    vr.n_patients,
        "n_events":      vr.n_events,
        "AUC":           round(vr.auc, 3) if math.isfinite(vr.auc) else "",
        "AUC_95CI":      _fmt_ci(vr.auc_ci_lower, vr.auc_ci_upper),
        "Brier":         round(vr.brier_score, 3) if math.isfinite(vr.brier_score) else "",
        "Brier_95CI":    _fmt_ci(vr.brier_ci_lower, vr.brier_ci_upper),
        "Cal_slope":     round(vr.cal_slope, 3) if math.isfinite(vr.cal_slope) else "",
        "Cal_intercept": round(vr.cal_intercept, 3) if math.isfinite(vr.cal_intercept) else "",
        "HL_stat":       round(vr.hl_stat, 2) if math.isfinite(vr.hl_stat) else "",
        "HL_p":          round(hl_p, 3) if math.isfinite(hl_p) else "",
        "ECE":           round(vr.ece, 3) if math.isfinite(vr.ece) else "",
        "cal_adequate":  vr.hl_p_value > 0.05 if not math.isnan(vr.hl_p_value) else None,
    }
