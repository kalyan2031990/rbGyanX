# validation/cohort_consistency.py

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


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
