"""Patient setup error uncertainty via DVH dose-axis shifts (van Herk 1995)."""

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
class SetupErrorConfig:
    """Patient setup error parameters from CBCT analysis."""

    systematic_sigma_mm: float = 3.0
    random_sigma_mm: float = 2.0
    penumbra_mm: float = 10.0
    dose_gradient_gy_per_mm: float | None = None
    n_samples: int = 1000
    seed: int = 42


def _estimate_dose_gradient(dvh_df: pd.DataFrame, penumbra_mm: float = 10.0) -> float:
    """
    Estimate dose gradient G (Gy/mm): G_approx = (D5% − D95%) / (2 × penumbra_mm).
    """
    if dvh_df is None or dvh_df.empty:
        return 0.0
    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols = np.asarray(dvh_df["volume_frac"], dtype=float)
    if vols.sum() <= 0:
        return 0.0
    order = np.argsort(doses)
    doses_sorted = doses[order]
    cum_vol = np.cumsum(vols[order])
    cum_vol /= cum_vol[-1]

    d95 = float(np.interp(0.05, cum_vol, doses_sorted))
    d5 = float(np.interp(0.95, cum_vol, doses_sorted))
    gradient = (d5 - d95) / (2.0 * penumbra_mm) if penumbra_mm > 0 else 0.0
    return max(gradient, 0.0)


def _shift_dvh(dvh_df: pd.DataFrame, shift_gy: float) -> pd.DataFrame:
    """Return copy of dvh_df with dose axis shifted by shift_gy."""
    shifted = dvh_df.copy()
    shifted["dose_gy"] = np.clip(shifted["dose_gy"] + shift_gy, 0.0, None)
    return shifted


def run_setup_error_mc(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    site_params: TCPSiteParams,
    target_type: str = "GTV",
    config: SetupErrorConfig | None = None,
) -> dict:
    """
    MC TCP uncertainty from patient setup errors (van Herk 1995).

    σ_dose_gy = G × √(Σ_pop² + σ_pop²/n_fractions)
    """
    if config is None:
        config = SetupErrorConfig()

    g = config.dose_gradient_gy_per_mm
    if g is None:
        g = _estimate_dose_gradient(dvh_df, config.penumbra_mm)

    sigma_geom = math.sqrt(
        config.systematic_sigma_mm**2
        + config.random_sigma_mm**2 / max(n_fractions, 1)
    )
    g_used = g
    sigma_dose_gy = g_used * sigma_geom

    rng = np.random.default_rng(config.seed)
    n = config.n_samples
    shift_sd = sigma_dose_gy if sigma_dose_gy > 0 else 1e-9
    shifts_gy = rng.normal(0.0, shift_sd, size=n)

    poisson_calc = PoissonTCPCalculator()
    zm_calc = ZMTCPCalculator()
    geud_calc = GEUDTCPCalculator()
    logistic_calc = LogisticTCPCalculator()

    tcp_poisson = np.full(n, math.nan)
    tcp_zm = np.full(n, math.nan)
    tcp_geud = np.full(n, math.nan)
    tcp_logistic = np.full(n, math.nan)

    for i, shift in enumerate(shifts_gy):
        dvh_shifted = _shift_dvh(dvh_df, float(shift))
        try:
            tcp_poisson[i] = poisson_calc.compute_tcp_dvh(
                dvh_shifted, n_fractions, site_params, target_type
            )["tcp"]
        except Exception:
            pass
        try:
            tcp_zm[i] = zm_calc.compute_tcp_dvh(
                dvh_shifted, n_fractions, site_params, target_type
            )["tcp"]
        except Exception:
            pass
        try:
            tcp_geud[i] = geud_calc.compute_tcp(dvh_shifted, site_params)["tcp"]
        except Exception:
            pass
        try:
            tcp_logistic[i] = logistic_calc.compute_tcp(dvh_shifted, site_params)["tcp"]
        except Exception:
            pass

    return {
        "TCP_Poisson_setup_mc": _aggregate_mc(tcp_poisson),
        "TCP_ZM_setup_mc": _aggregate_mc(tcp_zm),
        "TCP_gEUD_setup_mc": _aggregate_mc(tcp_geud),
        "TCP_Logistic_setup_mc": _aggregate_mc(tcp_logistic),
        "estimated_dose_gradient_gy_per_mm": g_used,
        "sigma_geom_mm": sigma_geom,
        "sigma_dose_gy": sigma_dose_gy,
        "n_samples": n,
        "setup_config": {
            "systematic_sigma_mm": config.systematic_sigma_mm,
            "random_sigma_mm": config.random_sigma_mm,
            "penumbra_mm": config.penumbra_mm,
        },
    }
