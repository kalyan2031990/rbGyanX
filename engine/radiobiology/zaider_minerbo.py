"""
Zaider-Minerbo (ZM) stochastic TCP model.

Uses Poisson-LQ N_eff from compute_n_eff_from_dvh, then birth-death extinction p0 —
standard clinical approximation of the full ZM model (Zaider & Minerbo, Phys Med Biol 2000).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from radiobiology import lq_model
from radiobiology.poisson_tcp import compute_n_eff_from_dvh, _dvh_dmean, _dvh_d95

if TYPE_CHECKING:
    from config.site_params import TCPSiteParams

logger = logging.getLogger(__name__)


class ZMTCPCalculator:
    """Zaider-Minerbo TCP using birth-death extinction probability."""

    def __init__(self, dead_fraction: float = 0.85, t_obs_days: float = 730.0):
        self.dead_fraction = dead_fraction
        self.t_obs_days = t_obs_days

    def _p0_single_cell(self, t: float, b: float, mu: float) -> float:
        """Extinction probability for a single cell at time t post-treatment."""
        if t <= 0:
            return 0.0
        if mu > b:
            return 1.0
        if abs(b - mu) < 1e-12:
            return float(b * t / (1.0 + b * t))
        exp_term = math.exp(-(b - mu) * t)
        numerator = mu * (1.0 - exp_term)
        denominator = b - mu * exp_term
        if abs(denominator) < 1e-15:
            return math.nan
        return float(np.clip(numerator / denominator, 0.0, 1.0))

    def _rates(self, site_params: TCPSiteParams) -> tuple[float, float]:
        b = math.log(2) / site_params.Tpot_days
        mu = b * self.dead_fraction
        return b, mu

    def compute_tcp_uniform(
        self,
        total_dose_gy: float,
        n_fractions: int,
        site_params: TCPSiteParams,
        target_type: str = "GTV",
        treatment_time_days: float | None = None,
    ) -> dict:
        from radiobiology.poisson_tcp import PoissonTCPCalculator

        poisson = PoissonTCPCalculator().compute_tcp_uniform(
            total_dose_gy,
            n_fractions,
            site_params,
            target_type,
            treatment_time_days,
        )
        b, mu = self._rates(site_params)
        p0 = self._p0_single_cell(self.t_obs_days, b, mu)
        n_eff = poisson["N_eff"]
        tcp = math.nan
        if not math.isnan(n_eff) and not math.isnan(p0):
            tcp = float(np.clip(p0**n_eff, 0.0, 1.0))

        return {
            **poisson,
            "tcp": tcp,
            "p0_single_cell": p0,
            "b_rate": b,
            "mu_rate": mu,
            "model": "Zaider-Minerbo",
        }

    def compute_tcp_dvh(
        self,
        dvh_df: pd.DataFrame,
        n_fractions: int,
        site_params: TCPSiteParams,
        target_type: str = "GTV",
        treatment_time_days: float | None = None,
    ) -> dict:
        t_days = (
            treatment_time_days
            if treatment_time_days is not None
            else lq_model.treatment_time_days(n_fractions)
        )
        n_eff, sf_weighted, repop = compute_n_eff_from_dvh(
            dvh_df, n_fractions, site_params, target_type, t_days
        )
        b, mu = self._rates(site_params)
        # Approximation: p0 at t_obs; N_eff accounts for repopulation during treatment.
        p0 = self._p0_single_cell(self.t_obs_days, b, mu)
        tcp = math.nan
        if not math.isnan(n_eff) and not math.isnan(p0):
            tcp = float(np.clip(p0**n_eff, 0.0, 1.0))

        dmean = _dvh_dmean(dvh_df)
        d95 = _dvh_d95(dvh_df)
        dpf = dmean / n_fractions if n_fractions > 0 and not math.isnan(dmean) else math.nan
        use_usc = not math.isnan(dpf) and dpf > site_params.lq_valid_max_dpf_gy

        from radiobiology.lq_model import bed, eqd2, eqd2_usc

        bed_gy = bed(dmean, dpf, site_params.alpha_beta_gy) if not math.isnan(dmean) else math.nan
        if use_usc and not math.isnan(dmean):
            eqd2_gy = eqd2_usc(
                dmean, dpf, site_params.alpha_beta_gy, site_params.lq_valid_max_dpf_gy
            )
        elif not math.isnan(dmean):
            eqd2_gy = eqd2(dmean, dpf, site_params.alpha_beta_gy)
        else:
            eqd2_gy = math.nan

        return {
            "tcp": tcp,
            "N_eff": n_eff,
            "SF_total": sf_weighted,
            "BED_gy": bed_gy,
            "EQD2_gy": eqd2_gy,
            "repop_factor": repop,
            "lq_caution": use_usc,
            "p0_single_cell": p0,
            "b_rate": b,
            "mu_rate": mu,
            "model": "Zaider-Minerbo",
            "Dmean_gy": dmean,
            "D95_gy": d95,
            "dvh_bins": 0 if dvh_df is None or dvh_df.empty else len(dvh_df),
        }
