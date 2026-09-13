"""Consensus combiners for uTCP / uNTCP (paper §2.C).

Historically the only combiner was inverse-variance weighting (Eq. 1). Analysis B
(``analysis/preregistration_B.md``, ``docs/CONSENSUS_B_RESULTS.md``) showed that
inverse-variance weighting of *same-endpoint* radiobiological models is
mechanistically fragile: because ``w_i = 1/sigma_i**2``, a single over-confident
member (narrow parametric band) captures almost all the weight and propagates its
error into the consensus — up to +0.24 Brier damage in the pre-registered stress
test — even when it is confidently *wrong*. A rank-based (median) combiner is
invariant to any single member's quoted confidence and removed that failure at no
cost on the clean cohort.

The engine therefore now defaults to the **robust median** combiner. Inverse-variance
weighting and a disagreement-penalised variant remain available and are selectable via
``method=`` for reproducibility and for the well-specified/independent case where
inverse-variance weighting is genuinely MSE-optimal (see B11 analytic note).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np

# Robust median is the default; the historical inverse-variance combiner and a
# disagreement-penalised variant stay selectable.
DEFAULT_METHOD = "median"
VALID_METHODS = ("median", "inverse_variance", "disagreement")


def _empty(method: str) -> dict[str, float | list[float] | str]:
    return {
        "mean": math.nan,
        "variance": math.nan,
        "within_model_variance": math.nan,
        "tau_squared": math.nan,
        "sd": math.nan,
        "weights": [],
        "method": method,
    }


def _clean(
    estimates: Sequence[float], variances: Sequence[float]
) -> tuple[np.ndarray, np.ndarray] | None:
    est = np.asarray(estimates, dtype=float)
    var = np.asarray(variances, dtype=float)
    mask = np.isfinite(est) & np.isfinite(var) & (var > 0)
    if not np.any(mask):
        return None
    return est[mask], var[mask]


def inverse_variance_consensus(
    estimates: Sequence[float],
    variances: Sequence[float],
) -> dict[str, float | list[float]]:
    """
    Combine model estimates with weights w_i = 1/sigma_i**2 (historical combiner).

    Combined variance = 1/Sum(w_i) + tau**2 where tau**2 = Var_i(P_i) is the
    between-model spread. Kept for reproducibility and for the well-specified,
    independent case; NOT the engine default (see module docstring / Analysis B).
    """
    cleaned = _clean(estimates, variances)
    if cleaned is None:
        out = _empty("inverse_variance")
        del out["method"]  # preserve the historical return shape for this entry point
        return out
    est, var = cleaned
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


def disagreement_penalty_consensus(
    estimates: Sequence[float],
    variances: Sequence[float],
) -> dict[str, float | list[float] | str]:
    """Inverse-variance weighting with each variance inflated by the between-model
    spread: sigma_i**2 <- sigma_i**2 + tau**2. This down-weights a lone confident
    outlier (its effective weight can no longer diverge), a middle ground between
    naive inverse-variance and the median (B5)."""
    cleaned = _clean(estimates, variances)
    if cleaned is None:
        return _empty("disagreement")
    est, var = cleaned
    tau_sq = float(np.var(est, ddof=1)) if len(est) > 1 else 0.0
    eff_var = var + tau_sq
    weights = 1.0 / eff_var
    w_sum = float(np.sum(weights))
    mean = float(np.sum(weights * est) / w_sum)
    within = 1.0 / w_sum
    total_var = within + tau_sq
    return {
        "mean": mean,
        "variance": float(total_var),
        "within_model_variance": float(within),
        "tau_squared": tau_sq,
        "sd": float(math.sqrt(total_var)),
        "weights": weights.tolist(),
        "method": "disagreement",
    }


def robust_median_consensus(
    estimates: Sequence[float],
    variances: Sequence[float],
) -> dict[str, float | list[float] | str]:
    """Robust consensus: the point estimate is the **median** of the member
    estimates, so no single member's quoted confidence can move it (breakdown
    point ~50%). The band uses the between-model spread tau**2 plus the *median*
    within-model variance (a robust central within-model term), so an
    artificially narrow or wide member cannot collapse or inflate the band.

    This is the engine default (Analysis B). ``weights`` is reported empty because
    the estimator is rank-based, not a linear weighting.
    """
    cleaned = _clean(estimates, variances)
    if cleaned is None:
        return _empty("median")
    est, var = cleaned
    mean = float(np.median(est))
    tau_sq = float(np.var(est, ddof=1)) if len(est) > 1 else 0.0
    within = float(np.median(var))
    total_var = within + tau_sq
    return {
        "mean": mean,
        "variance": float(total_var),
        "within_model_variance": float(within),
        "tau_squared": tau_sq,
        "sd": float(math.sqrt(total_var)),
        "weights": [],
        "method": "median",
    }


_COMBINERS = {
    "median": robust_median_consensus,
    "inverse_variance": inverse_variance_consensus,
    "disagreement": disagreement_penalty_consensus,
}


def combine_consensus(
    estimates: Sequence[float],
    variances: Sequence[float],
    method: str = DEFAULT_METHOD,
) -> dict[str, float | list[float] | str]:
    """Dispatch to the requested consensus combiner (default: robust ``median``).

    ``method`` is one of ``median`` (default, robust), ``inverse_variance``
    (historical, MSE-optimal only for independent, unbiased, well-specified
    members), or ``disagreement`` (inverse-variance with a between-model penalty).
    The returned dict always carries a ``method`` key naming the combiner used.
    """
    if method not in _COMBINERS:
        raise ValueError(f"unknown consensus method {method!r}; choose from {VALID_METHODS}")
    out = _COMBINERS[method](estimates, variances)
    out.setdefault("method", method)  # inverse_variance keeps its historical shape otherwise
    return out
