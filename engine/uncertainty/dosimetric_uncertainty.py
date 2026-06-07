"""Systematic and random dose delivery uncertainty (ICRU 91 / TG-119)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.site_params import TCPSiteParams
from radiobiology.geud_tcp import GEUDTCPCalculator
from radiobiology.logistic_tcp import LogisticTCPCalculator
from radiobiology.poisson_tcp import PoissonTCPCalculator
from radiobiology.zaider_minerbo import ZMTCPCalculator
from uncertainty.parameter_mc import _aggregate_mc

logger = logging.getLogger(__name__)


@dataclass
class DosimetricUncertaintyConfig:
    """Systematic and random dose delivery uncertainty (% 1-sigma)."""

    systematic_dose_sigma_pct: float = 2.0
    random_dose_sigma_pct: float = 1.5
    n_samples: int = 1000
    seed: int = 42


def _scale_dvh(dvh_df: pd.DataFrame, scale_factor: float) -> pd.DataFrame:
    """Return a copy of dvh_df with dose_gy multiplied by scale_factor."""
    scaled = dvh_df.copy()
    scaled["dose_gy"] = np.clip(scaled["dose_gy"] * scale_factor, 0.0, None)
    return scaled


def run_dosimetric_mc(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    site_params: TCPSiteParams,
    target_type: str = "GTV",
    config: DosimetricUncertaintyConfig | None = None,
) -> dict:
    """
    MC dose uncertainty propagation.

    σ_eff = √( (σ_sys/100)² + (σ_rand/100)²/n_fractions )
    """
    if config is None:
        config = DosimetricUncertaintyConfig()

    sigma_sys = config.systematic_dose_sigma_pct / 100.0
    sigma_rand = config.random_dose_sigma_pct / 100.0
    sigma_eff = math.sqrt(sigma_sys**2 + sigma_rand**2 / max(n_fractions, 1))

    rng = np.random.default_rng(config.seed)
    scale_factors = rng.normal(1.0, sigma_eff, size=config.n_samples)
    scale_factors = np.clip(scale_factors, 0.01, None)

    poisson_calc = PoissonTCPCalculator()
    zm_calc = ZMTCPCalculator()
    geud_calc = GEUDTCPCalculator()
    logistic_calc = LogisticTCPCalculator()

    n = config.n_samples
    tcp_poisson = np.full(n, math.nan)
    tcp_zm = np.full(n, math.nan)
    tcp_geud = np.full(n, math.nan)
    tcp_logistic = np.full(n, math.nan)

    for i, sf in enumerate(scale_factors):
        dvh_scaled = _scale_dvh(dvh_df, float(sf))
        try:
            tcp_poisson[i] = poisson_calc.compute_tcp_dvh(
                dvh_scaled, n_fractions, site_params, target_type
            )["tcp"]
        except Exception:
            pass
        try:
            tcp_zm[i] = zm_calc.compute_tcp_dvh(
                dvh_scaled, n_fractions, site_params, target_type
            )["tcp"]
        except Exception:
            pass
        try:
            tcp_geud[i] = geud_calc.compute_tcp(dvh_scaled, site_params)["tcp"]
        except Exception:
            pass
        try:
            tcp_logistic[i] = logistic_calc.compute_tcp(dvh_scaled, site_params)["tcp"]
        except Exception:
            pass

    return {
        "TCP_Poisson_dose_mc": _aggregate_mc(tcp_poisson),
        "TCP_ZM_dose_mc": _aggregate_mc(tcp_zm),
        "TCP_gEUD_dose_mc": _aggregate_mc(tcp_geud),
        "TCP_Logistic_dose_mc": _aggregate_mc(tcp_logistic),
        "sigma_eff_pct": math.sqrt(
            config.systematic_dose_sigma_pct**2
            + config.random_dose_sigma_pct**2 / max(n_fractions, 1)
        ),
        "n_samples": n,
        "dosimetric_config": {
            "systematic_sigma_pct": config.systematic_dose_sigma_pct,
            "random_sigma_pct": config.random_dose_sigma_pct,
        },
    }
