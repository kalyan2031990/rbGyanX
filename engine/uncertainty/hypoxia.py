"""OER-based hypoxia correction (Wouters & Brown 1997 DMF approach)."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from config.site_params import TCPSiteParams
from radiobiology.geud_tcp import compute_geud, geud_tcp_niemierko
from radiobiology.lq_model import survival_fraction
from radiobiology.poisson_tcp import _dvh_dmean, _n0_for_target, _repop_factor

logger = logging.getLogger(__name__)

SITE_HYPOXIC_FRACTION: dict[str, float] = {
    "HN": 0.30,
    "LUNG": 0.20,
    "LUNG_SBRT": 0.20,
    "BRAIN_GBM": 0.15,
    "BRAIN_METS": 0.10,
    "BREAST": 0.10,
}


@dataclass
class HypoxiaConfig:
    """Hypoxia correction configuration."""

    hypoxic_fraction: float | None = None
    oer: float = 2.5


def _get_hypoxic_fraction(site_params: TCPSiteParams, config: HypoxiaConfig) -> float:
    """Return hypoxic fraction: explicit config value, or site default."""
    if config.hypoxic_fraction is not None:
        return float(config.hypoxic_fraction)
    return float(SITE_HYPOXIC_FRACTION.get(site_params.site, 0.10))


def _compute_sf_total_hypoxia(
    dose_gy_bin: float,
    n_fractions: int,
    alpha_eff: float,
    beta_eff: float,
    d_transition_gy: float,
) -> float:
    """SF_total for one DVH bin using effective (OER-modified) α_eff and β_eff."""
    if dose_gy_bin <= 0 or n_fractions <= 0:
        return 1.0
    dpf = dose_gy_bin / n_fractions
    use_usc = dpf > d_transition_gy
    sf_per_frac = survival_fraction(
        dpf,
        alpha_eff,
        beta_eff,
        d_transition_gy=d_transition_gy,
        use_usc=use_usc,
    )
    if math.isnan(sf_per_frac):
        return math.nan
    return float(sf_per_frac**n_fractions)


def apply_hypoxia_correction(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    site_params: TCPSiteParams,
    target_type: str = "GTV",
    treatment_time_days: float | None = None,
    config: HypoxiaConfig | None = None,
) -> dict:
    """
    Compute hypoxia-corrected TCP for Poisson, gEUD, and Logistic models.

    Two-population parallel model (Wouters & Brown 1997).
    """
    if config is None:
        config = HypoxiaConfig()

    hf = _get_hypoxic_fraction(site_params, config)
    oer = config.oer

    alpha = float(site_params.alpha_gy_inv)
    beta = float(site_params.beta_gy_inv2)
    alpha_hyp = alpha / oer
    beta_hyp = beta / oer**2
    d_t = site_params.lq_valid_max_dpf_gy

    from radiobiology import lq_model

    t_days = (
        treatment_time_days
        if treatment_time_days is not None
        else lq_model.treatment_time_days(n_fractions)
    )
    repop = _repop_factor(site_params, t_days)
    n0 = _n0_for_target(site_params, target_type)

    tcp_poisson_hyp = math.nan
    if dvh_df is not None and not dvh_df.empty:
        n_eff = 0.0
        valid = True
        for _, row in dvh_df.iterrows():
            dose = float(row["dose_gy"])
            vol = float(row["volume_frac"])
            sf_oxy = _compute_sf_total_hypoxia(
                dose, n_fractions, alpha, beta, d_t
            )
            sf_hyp = _compute_sf_total_hypoxia(
                dose, n_fractions, alpha_hyp, beta_hyp, d_t
            )
            if math.isnan(sf_oxy) or math.isnan(sf_hyp):
                valid = False
                break
            n_eff += n0 * vol * ((1.0 - hf) * sf_oxy + hf * sf_hyp)
        if valid:
            n_eff *= repop
            tcp_poisson_hyp = float(np.clip(math.exp(-n_eff), 0.0, 1.0))

    geud_gy = compute_geud(dvh_df, site_params.geud_a)
    tcd50_eff_geud = float(site_params.TCD50_gy) * (1.0 + hf * (oer - 1.0))
    tcp_geud_hyp = geud_tcp_niemierko(
        geud_gy, tcd50_eff_geud, float(site_params.gamma50)
    )

    dmean = _dvh_dmean(dvh_df) if dvh_df is not None and not dvh_df.empty else math.nan
    tcp_logistic_hyp = math.nan
    if not math.isnan(dmean) and dmean > 0:
        d50_eff = float(site_params.D50_logistic_gy) * (1.0 + hf * (oer - 1.0))
        tcp_logistic_hyp = float(
            np.clip(
                1.0 / (1.0 + (d50_eff / dmean) ** float(site_params.k_logistic)),
                0.0,
                1.0,
            )
        )

    return {
        "TCP_Poisson_hypoxia": tcp_poisson_hyp,
        "TCP_gEUD_hypoxia": tcp_geud_hyp,
        "TCP_Logistic_hypoxia": tcp_logistic_hyp,
        "hypoxic_fraction": hf,
        "oer": oer,
        "alpha_hyp": alpha_hyp,
        "beta_hyp": beta_hyp,
        "TCD50_eff_geud": tcd50_eff_geud,
        "site": site_params.site,
    }
