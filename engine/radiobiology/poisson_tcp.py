"""Poisson-LQ TCP model with optional repopulation."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

from radiobiology import lq_model
from radiobiology.lq_model import bed, eqd2, eqd2_usc, survival_fraction

if TYPE_CHECKING:
    from config.site_params import TCPSiteParams

logger = logging.getLogger(__name__)

_N0_MAP_KEYS = ("GTV", "CTV", "PTV")


def _n0_for_target(site_params: TCPSiteParams, target_type: str) -> float:
    mapping = {
        "GTV": site_params.N0_gtv,
        "CTV": site_params.N0_ctv,
        "PTV": site_params.N0_ctv,
    }
    return float(mapping.get(target_type.upper(), site_params.N0_gtv))


def _repop_factor(site_params: TCPSiteParams, treatment_days: float) -> float:
    if not site_params.repopulation_relevant or site_params.Tk_days is None:
        return 1.0
    repop_days = max(0.0, treatment_days - float(site_params.Tk_days))
    return float(math.exp(math.log(2) * repop_days / site_params.Tpot_days))


def _sf_total_per_bin(
    total_dose_bin_gy: float,
    n_fractions: int,
    alpha: float,
    beta: float,
    site_params: TCPSiteParams,
) -> float:
    if total_dose_bin_gy <= 0:
        return 1.0
    d_i = total_dose_bin_gy / n_fractions
    use_usc = d_i > site_params.lq_valid_max_dpf_gy
    sf_frac = survival_fraction(
        d_i,
        alpha,
        beta,
        d_transition_gy=site_params.lq_valid_max_dpf_gy,
        use_usc=use_usc,
    )
    if math.isnan(sf_frac):
        return math.nan
    return float(sf_frac**n_fractions)


def _dvh_dmean(dvh_df: pd.DataFrame) -> float:
    if dvh_df is None or dvh_df.empty:
        return math.nan
    total_vol = float(dvh_df["volume_frac"].sum())
    if total_vol <= 0:
        return math.nan
    if abs(total_vol - 1.0) > 0.05:
        logger.warning(
            "DVH volume_frac sums to %.4f (expected ~1.0); normalising for Dmean. "
            "Check DVH binning/conversion.",
            total_vol,
        )
    return float((dvh_df["dose_gy"] * dvh_df["volume_frac"]).sum() / total_vol)


def _dvh_d95(dvh_df: pd.DataFrame) -> float:
    if dvh_df is None or dvh_df.empty:
        return math.nan
    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols = np.asarray(dvh_df["volume_frac"], dtype=float)
    if vols.sum() <= 0:
        return math.nan
    order = np.argsort(doses)
    doses = doses[order]
    vols = vols[order]
    cum = np.cumsum(vols)
    idx = int(np.searchsorted(cum, 0.05, side="left"))
    idx = min(idx, len(doses) - 1)
    return float(doses[idx])


def compute_n_eff_from_dvh(
    dvh_df: pd.DataFrame,
    n_fractions: int,
    site_params: TCPSiteParams,
    target_type: str,
    treatment_time_days_val: float,
) -> tuple[float, float, float]:
    """Return (N_eff, SF_total_weighted, repop_factor). Vectorised."""
    alpha = site_params.alpha_gy_inv
    beta = site_params.beta_gy_inv2
    n0 = _n0_for_target(site_params, target_type)
    repop = _repop_factor(site_params, treatment_time_days_val)

    if dvh_df is None or dvh_df.empty:
        return math.nan, math.nan, repop

    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols = np.asarray(dvh_df["volume_frac"], dtype=float)
    total_vol = vols.sum()
    if total_vol <= 0:
        return math.nan, math.nan, repop
    if abs(total_vol - 1.0) > 0.05:
        logger.warning(
            "DVH volume_frac sums to %.4f (expected ~1.0); normalising for N_eff.",
            total_vol,
        )
    vols = vols / total_vol

    d_transition = site_params.lq_valid_max_dpf_gy
    d_per_fx = doses / n_fractions if n_fractions > 0 else doses
    use_usc = d_per_fx > d_transition

    sf_lq = np.exp(-alpha * d_per_fx - beta * d_per_fx**2)
    exponent_usc = -(d_per_fx * (alpha + 2 * beta * d_transition) - beta * d_transition**2)
    sf_usc = np.exp(exponent_usc)
    sf_per_fx = np.where(use_usc, sf_usc, sf_lq)
    sf_total = sf_per_fx**n_fractions
    sf_total = np.where(doses <= 0, 1.0, sf_total)

    valid = np.isfinite(sf_total)
    n_eff = float(np.sum(n0 * vols[valid] * sf_total[valid])) * repop
    sf_weighted = float(np.sum(vols[valid] * sf_total[valid]))

    return n_eff, sf_weighted, repop


class PoissonTCPCalculator:
    """Poisson-LQ TCP with repopulation correction."""

    def compute_tcp_uniform(
        self,
        total_dose_gy: float,
        n_fractions: int,
        site_params: TCPSiteParams,
        target_type: str = "GTV",
        treatment_time_days: float | None = None,
    ) -> dict:
        dpf = total_dose_gy / n_fractions if n_fractions > 0 else math.nan
        t_days = (
            treatment_time_days
            if treatment_time_days is not None
            else lq_model.treatment_time_days(n_fractions)
        )
        alpha = site_params.alpha_gy_inv
        beta = site_params.beta_gy_inv2
        n0 = _n0_for_target(site_params, target_type)
        sf_total = _sf_total_per_bin(total_dose_gy, n_fractions, alpha, beta, site_params)
        repop = _repop_factor(site_params, t_days)
        n_eff = n0 * sf_total * repop
        tcp = math.nan
        if not math.isnan(n_eff):
            tcp = float(np.clip(math.exp(-n_eff), 0.0, 1.0))

        use_usc = dpf > site_params.lq_valid_max_dpf_gy
        bed_gy = bed(total_dose_gy, dpf, site_params.alpha_beta_gy)
        if use_usc:
            eqd2_gy = eqd2_usc(
                total_dose_gy,
                dpf,
                site_params.alpha_beta_gy,
                site_params.lq_valid_max_dpf_gy,
            )
        else:
            eqd2_gy = eqd2(total_dose_gy, dpf, site_params.alpha_beta_gy)

        return {
            "tcp": tcp,
            "N_eff": n_eff,
            "SF_total": sf_total,
            "BED_gy": bed_gy,
            "EQD2_gy": eqd2_gy,
            "repop_factor": repop,
            "lq_caution": use_usc,
            "model": "Poisson-LQ",
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
        tcp = math.nan
        if not math.isnan(n_eff):
            tcp = float(np.clip(math.exp(-n_eff), 0.0, 1.0))

        dmean = _dvh_dmean(dvh_df)
        d95 = _dvh_d95(dvh_df)
        n_bins = 0 if dvh_df is None or dvh_df.empty else len(dvh_df)

        dpf = dmean / n_fractions if n_fractions > 0 and not math.isnan(dmean) else math.nan
        use_usc = not math.isnan(dpf) and dpf > site_params.lq_valid_max_dpf_gy
        bed_gy = (
            bed(dmean, dpf, site_params.alpha_beta_gy) if not math.isnan(dmean) else math.nan
        )
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
            "model": "Poisson-LQ",
            "Dmean_gy": dmean,
            "D95_gy": d95,
            "dvh_bins": n_bins,
        }
