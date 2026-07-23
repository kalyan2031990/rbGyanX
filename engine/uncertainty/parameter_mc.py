"""Monte Carlo uncertainty propagation over radiobiological parameters."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd
from scipy import stats

from config.site_params import TCPSiteParams
from radiobiology.geud_tcp import GEUDTCPCalculator
from radiobiology.logistic_tcp import LogisticTCPCalculator
from radiobiology.poisson_tcp import PoissonTCPCalculator
from radiobiology.zaider_minerbo import ZMTCPCalculator

logger = logging.getLogger(__name__)


@dataclass
class ParamUncertaintyConfig:
    """
    Coefficient of variation (CV) for each radiobiological parameter.
    CV = SD / mean. For N0, log10_sigma is the SD on the log10 scale.
    """

    alpha_cv: float = 0.15
    beta_cv: float = 0.20
    N0_log10_sigma: float = 0.50
    TCD50_cv: float = 0.12
    gamma50_cv: float = 0.15
    n_samples: int = 1000
    seed: int = 42
    store_samples: bool = False


def _truncated_normal_samples(
    mean: float, cv: float, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw n samples from a normal distribution truncated at 0."""
    sd = abs(mean) * cv
    if sd <= 0 or mean <= 0:
        return np.full(n, mean)
    a = -mean / sd
    b = np.inf
    return stats.truncnorm.rvs(a, b, loc=mean, scale=sd, size=n, random_state=rng)


def _lognormal_samples(
    mean: float, log10_sigma: float, n: int, rng: np.random.Generator
) -> np.ndarray:
    """Draw n samples from log-normal: log10(N0) ~ N(log10(mean), log10_sigma)."""
    log10_mean = math.log10(mean)
    log10_samples = rng.normal(log10_mean, log10_sigma, size=n)
    return np.power(10.0, log10_samples)


def _aggregate_mc(samples: np.ndarray) -> dict:
    """Compute mean, SD, P5, P95 from a 1-D array of TCP values."""
    valid = samples[np.isfinite(samples)]
    if len(valid) == 0:
        return {
            "mean": math.nan,
            "sd": math.nan,
            "p5": math.nan,
            "p95": math.nan,
            "n_valid": 0,
        }
    return {
        "mean": float(np.mean(valid)),
        "sd": float(np.std(valid, ddof=1)),
        "p5": float(np.percentile(valid, 5)),
        "p95": float(np.percentile(valid, 95)),
        "n_valid": int(len(valid)),
    }


def run_parameter_mc(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    site_params: TCPSiteParams,
    target_type: str = "GTV",
    config: ParamUncertaintyConfig | None = None,
) -> dict:
    """
    Monte Carlo uncertainty propagation over radiobiological parameters.

    For each sample: draw (α, β, N₀, TCD50, γ50), build perturbed TCPSiteParams,
    compute all four TCP models, collect TCPs.
    """
    if config is None:
        config = ParamUncertaintyConfig()

    rng = np.random.default_rng(config.seed)
    n = config.n_samples

    alpha_mean = float(site_params.alpha_gy_inv)
    beta_mean = float(site_params.beta_gy_inv2)
    n0_mean = float(site_params.N0_gtv)
    tcd50_mean = float(site_params.TCD50_gy)
    gamma_mean = float(site_params.gamma50)

    alpha_s = _truncated_normal_samples(alpha_mean, config.alpha_cv, n, rng)
    beta_s = _truncated_normal_samples(beta_mean, config.beta_cv, n, rng)
    n0_s = _lognormal_samples(n0_mean, config.N0_log10_sigma, n, rng)
    tcd50_s = _truncated_normal_samples(tcd50_mean, config.TCD50_cv, n, rng)
    gamma50_s = _truncated_normal_samples(gamma_mean, config.gamma50_cv, n, rng)

    poisson_calc = PoissonTCPCalculator()
    zm_calc = ZMTCPCalculator()
    geud_calc = GEUDTCPCalculator()
    logistic_calc = LogisticTCPCalculator()

    tcp_poisson = np.full(n, math.nan)
    tcp_zm = np.full(n, math.nan)
    tcp_geud = np.full(n, math.nan)
    tcp_logistic = np.full(n, math.nan)

    n0_ctv_mean = float(site_params.N0_ctv)
    n0_ratio = n0_ctv_mean / n0_mean if n0_mean > 0 else 1.0

    for i in range(n):
        ab = alpha_s[i] / beta_s[i] if beta_s[i] > 0 else site_params.alpha_beta_gy
        n0_ctv_s = n0_s[i] * n0_ratio
        sp = replace(
            site_params,
            alpha_gy_inv=float(alpha_s[i]),
            beta_gy_inv2=float(beta_s[i]),
            alpha_beta_gy=float(ab),
            N0_gtv=float(n0_s[i]),
            N0_ctv=float(n0_ctv_s),
            TCD50_gy=float(tcd50_s[i]),
            gamma50=float(gamma50_s[i]),
        )
        try:
            r = poisson_calc.compute_tcp_dvh(dvh_df, n_fractions, sp, target_type)
            tcp_poisson[i] = r["tcp"]
        except Exception:
            pass
        try:
            r = zm_calc.compute_tcp_dvh(dvh_df, n_fractions, sp, target_type)
            tcp_zm[i] = r["tcp"]
        except Exception:
            pass
        try:
            r = geud_calc.compute_tcp(dvh_df, sp)
            tcp_geud[i] = r["tcp"]
        except Exception:
            pass
        try:
            r = logistic_calc.compute_tcp(dvh_df, sp)
            tcp_logistic[i] = r["tcp"]
        except Exception:
            pass

    result = {
        "TCP_Poisson_mc": _aggregate_mc(tcp_poisson),
        "TCP_ZM_mc": _aggregate_mc(tcp_zm),
        "TCP_gEUD_mc": _aggregate_mc(tcp_geud),
        "TCP_Logistic_mc": _aggregate_mc(tcp_logistic),
        "n_samples": n,
        "param_uncertainty_config": {
            "alpha_cv": config.alpha_cv,
            "beta_cv": config.beta_cv,
            "N0_log10_sigma": config.N0_log10_sigma,
            "TCD50_cv": config.TCD50_cv,
            "gamma50_cv": config.gamma50_cv,
        },
    }
    if config.store_samples:
        result["_raw"] = {
            "TCP_Poisson": tcp_poisson,
            "TCP_ZM": tcp_zm,
            "TCP_gEUD": tcp_geud,
            "TCP_Logistic": tcp_logistic,
        }
    return result
