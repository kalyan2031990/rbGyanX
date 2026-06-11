"""uTCP consensus over classical TCP models (mirrors uNTCP machinery)."""

from __future__ import annotations

import math

import pandas as pd

from config.site_params import TCPSiteParams
from uncertainty.inverse_variance_consensus import inverse_variance_consensus
from uncertainty.parameter_mc import ParamUncertaintyConfig, run_parameter_mc


def run_utcp_consensus(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    site_params: TCPSiteParams,
    target_type: str = "GTV",
    config: ParamUncertaintyConfig | None = None,
) -> dict:
    """Inverse-variance consensus uTCP from per-model MC means and variances."""
    mc = run_parameter_mc(dvh_df, n_fractions, site_params, target_type, config)
    keys = ("TCP_Poisson_mc", "TCP_ZM_mc", "TCP_gEUD_mc", "TCP_Logistic_mc")
    estimates: list[float] = []
    variances: list[float] = []
    for key in keys:
        block = mc.get(key, {})
        mean = block.get("mean", math.nan)
        sd = block.get("sd", math.nan)
        if math.isfinite(mean) and math.isfinite(sd) and sd > 0:
            estimates.append(float(mean))
            variances.append(float(sd**2))
    consensus = inverse_variance_consensus(estimates, variances)
    return {
        "uTCP": consensus,
        "per_model_mc": {k: mc[k] for k in keys if k in mc},
        "n_samples": mc.get("n_samples"),
        "_note": "uTCP = inverse-variance consensus; UTCP (P+) is in radiobiology.utcp.",
    }
