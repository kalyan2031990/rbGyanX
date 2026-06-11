"""Inverse-variance consensus for uTCP / uNTCP (paper §2.C, Eq. 1)."""

from __future__ import annotations

import math
from typing import Sequence

import numpy as np


def inverse_variance_consensus(
    estimates: Sequence[float],
    variances: Sequence[float],
) -> dict[str, float | list[float]]:
    """
    Combine model estimates with weights w_i = 1/σ_i².

    Combined variance = 1/Σw_i + τ² where τ² = Var_i(P_i) is between-model spread.
    """
    est = np.asarray(estimates, dtype=float)
    var = np.asarray(variances, dtype=float)
    mask = np.isfinite(est) & np.isfinite(var) & (var > 0)
    if not np.any(mask):
        return {
            "mean": math.nan,
            "variance": math.nan,
            "within_model_variance": math.nan,
            "tau_squared": math.nan,
            "sd": math.nan,
            "weights": [],
        }
    est = est[mask]
    var = var[mask]
    weights = 1.0 / var
    w_sum = float(np.sum(weights))
    mean = float(np.sum(weights * est) / w_sum)
    within = 1.0 / w_sum
    tau_sq = float(np.var(est, ddof=1)) if len(est) > 1 else 0.0
    total_var = within + tau_sq
    return {
        "mean": mean,
        "variance": float(total_var),
        "within_model_variance": float(within),
        "tau_squared": tau_sq,
        "sd": float(math.sqrt(total_var)),
        "weights": weights.tolist(),
    }
