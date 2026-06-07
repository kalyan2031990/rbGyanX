"""uNTCP Monte Carlo parameter uncertainty for classical NTCP models."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats


@dataclass
class NTCPUncertaintyConfig:
    TD50_cv: float = 0.15
    m_cv: float = 0.25
    n_cv: float = 0.30
    gamma50_cv: float = 0.20
    D50_rs_cv: float = 0.15
    gamma_rs_cv: float = 0.20
    s_rs_cv: float = 0.25
    n_samples: int = 1000
    seed: int = 42


def _truncated_normal(mean: float, cv: float, n: int, rng: np.random.Generator) -> np.ndarray:
    sd = abs(mean) * cv
    if sd <= 0 or mean <= 0:
        return np.full(n, mean)
    a_clip = -mean / sd
    return stats.truncnorm.rvs(a_clip, np.inf, loc=mean, scale=sd, size=n, random_state=rng)


def _agg(arr: np.ndarray) -> dict:
    v = arr[np.isfinite(arr)]
    if len(v) == 0:
        return {"mean": math.nan, "sd": math.nan, "p5": math.nan, "p95": math.nan, "n_valid": 0}
    return {
        "mean": float(np.mean(v)),
        "sd": float(np.std(v, ddof=1)),
        "p5": float(np.percentile(v, 5)),
        "p95": float(np.percentile(v, 95)),
        "n_valid": int(len(v)),
    }


def run_untcp(
    dvh_df: pd.DataFrame,
    organ_params,
    config: NTCPUncertaintyConfig | None = None,
) -> dict:
    """Monte Carlo uncertainty bands for NTCP models."""
    from radiobiology.geud_tcp import compute_geud
    from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
    from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
    from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

    if config is None:
        config = NTCPUncertaintyConfig()
    rng = np.random.default_rng(config.seed)
    n = config.n_samples

    ll = organ_params.lkb_loglogit or {}
    pb = organ_params.lkb_probit or {}
    rs = organ_params.rs or {}

    TD50_ll = float(ll.get("TD50_gy", 0.0))
    g50_ll = float(ll.get("gamma50", 0.0))
    TD50_pb = float(pb.get("TD50_gy", 0.0))
    m_pb = float(pb.get("m", 0.0))
    n_pb = float(pb.get("n", 0.0))
    D50_rs = float(rs.get("D50_gy", 0.0))
    gamma_rs = float(rs.get("gamma", 0.0))
    s_rs = float(rs.get("s", 0.0))

    TD50_ll_s = _truncated_normal(TD50_ll, config.TD50_cv, n, rng) if TD50_ll > 0 else None
    g50_ll_s = _truncated_normal(g50_ll, config.gamma50_cv, n, rng) if g50_ll > 0 else None
    TD50_pb_s = _truncated_normal(TD50_pb, config.TD50_cv, n, rng) if TD50_pb > 0 else None
    m_pb_s = _truncated_normal(m_pb, config.m_cv, n, rng) if m_pb > 0 else None
    n_pb_s = _truncated_normal(n_pb, config.n_cv, n, rng) if n_pb > 0 else None
    D50_rs_s = _truncated_normal(D50_rs, config.D50_rs_cv, n, rng) if D50_rs > 0 else None
    g_rs_s = _truncated_normal(gamma_rs, config.gamma_rs_cv, n, rng) if gamma_rs > 0 else None
    s_rs_s = _truncated_normal(s_rs, config.s_rs_cv, n, rng) if s_rs > 0 else None

    ntcp_ll = np.full(n, math.nan)
    ntcp_pb = np.full(n, math.nan)
    ntcp_rs = np.full(n, math.nan)

    for i in range(n):
        if TD50_ll_s is not None and g50_ll_s is not None:
            geud_ll = compute_geud(dvh_df, organ_params.geud_a)
            ntcp_ll[i] = calculate_ntcp_lkb_loglogit(geud_ll, TD50_ll_s[i], g50_ll_s[i])
        if TD50_pb_s is not None and m_pb_s is not None and n_pb_s is not None:
            n_i = float(n_pb_s[i])
            if n_i > 0:
                geud_pb = compute_geud(dvh_df, a=1.0 / n_i)
                ntcp_pb[i] = calculate_ntcp_lkb_probit(geud_pb, TD50_pb_s[i], m_pb_s[i])
        if D50_rs_s is not None and g_rs_s is not None and s_rs_s is not None:
            ntcp_rs[i] = calculate_ntcp_rs_poisson(dvh_df, D50_rs_s[i], g_rs_s[i], s_rs_s[i])

    return {
        "uNTCP_LKB_loglogit": _agg(ntcp_ll),
        "uNTCP_LKB_probit": _agg(ntcp_pb),
        "uNTCP_RS": _agg(ntcp_rs),
        "n_samples": n,
        "organ": organ_params.canonical,
        "_note": "uNTCP uncertainty bands; UTCP (uncomplicated TCP) is different.",
    }
