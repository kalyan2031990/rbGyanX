# validation/cohort_consistency.py

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.covariance import MinCovDet


def _adaptive_ccs_threshold(n: int) -> float:
    """Threshold = max(0.20, 0.50 × min(n/50, 1.0))."""
    return max(0.20, 0.50 * min(n / 50.0, 1.0))


def compute_ccs(
    y_true: np.ndarray | pd.Series,
    y_prob_classical: np.ndarray,
    y_prob_ml: np.ndarray,
) -> dict:
    """
    Adaptive CCS: three Spearman correlations, adaptive threshold, verdict.
    """
    y = np.asarray(y_true, dtype=float)
    p_cl = np.asarray(y_prob_classical, dtype=float)
    p_ml = np.asarray(y_prob_ml, dtype=float)
    n = len(y)

    rho_cl_ml, _ = stats.spearmanr(p_cl, p_ml)
    rho_cl_out, _ = stats.spearmanr(p_cl, y)
    rho_ml_out, _ = stats.spearmanr(p_ml, y)

    ccs = float(np.mean([rho_cl_ml, rho_cl_out, rho_ml_out]))
    threshold = _adaptive_ccs_threshold(n)
    if ccs >= threshold:
        verdict = "CONSISTENT"
    elif ccs >= 0.5 * threshold:
        verdict = "MARGINAL"
    else:
        verdict = "INCONSISTENT"

    return {
        "ccs": ccs,
        "verdict": verdict,
        "threshold_used": threshold,
        "rho_classical_vs_ml": float(rho_cl_ml),
        "rho_classical_vs_outcome": float(rho_cl_out),
        "rho_ml_vs_outcome": float(rho_ml_out),
        "n_patients": n,
    }


def _mahalanobis_sq(
    X: np.ndarray,
    location: np.ndarray,
    covariance: np.ndarray,
) -> np.ndarray:
    diff = X - location
    inv = np.linalg.pinv(covariance)
    return np.einsum("...i,ij,...j->...", diff, inv, diff)


def compute_mcd_ccs(
    features: np.ndarray | pd.DataFrame,
    reference: np.ndarray | pd.DataFrame | None = None,
) -> dict:
    """
    Robust CCS via minimum-covariance-determinant Mahalanobis distance.

    Continuous CCS = F_{χ²_p}(d_M²); flag when d_M² > χ²_{p,0.975}.
    """
    X = np.asarray(features, dtype=float)
    if X.ndim != 2 or X.shape[0] < 2:
        return {"ccs": float("nan"), "flagged": [], "method": "mcd"}
    ref = np.asarray(reference, dtype=float) if reference is not None else X
    mcd = MinCovDet().fit(ref)
    dist_sq = np.asarray(mcd.mahalanobis(X), dtype=float)
    p = X.shape[1]
    chi2_crit = float(stats.chi2.ppf(0.975, p))
    ccs = stats.chi2.cdf(dist_sq, p)
    flagged = np.where(dist_sq > chi2_crit)[0].tolist()
    return {
        "ccs": ccs.tolist(),
        "mahalanobis_sq": dist_sq.tolist(),
        "chi2_critical": chi2_crit,
        "flagged_indices": flagged,
        "method": "mcd",
        "n_features": p,
    }


def compute_raw_covariance_ccs(
    features: np.ndarray | pd.DataFrame,
    reference: np.ndarray | pd.DataFrame | None = None,
) -> dict:
    """Sample-covariance Mahalanobis CCS (regression baseline; outlier-sensitive)."""
    X = np.asarray(features, dtype=float)
    ref = np.asarray(reference, dtype=float) if reference is not None else X
    loc = np.mean(ref, axis=0)
    cov = np.cov(ref, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])
    dist_sq = _mahalanobis_sq(X, loc, cov)
    p = X.shape[1]
    chi2_crit = float(stats.chi2.ppf(0.975, p))
    ccs = stats.chi2.cdf(dist_sq, p)
    flagged = np.where(dist_sq > chi2_crit)[0].tolist()
    return {
        "ccs": ccs.tolist(),
        "mahalanobis_sq": dist_sq.tolist(),
        "chi2_critical": chi2_crit,
        "flagged_indices": flagged,
        "method": "raw_covariance",
        "n_features": p,
    }
