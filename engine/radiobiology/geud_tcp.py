"""gEUD-based TCP (Niemierko)."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from config.site_params import TCPSiteParams

logger = logging.getLogger(__name__)


def compute_geud(dvh_df: pd.DataFrame, a: float) -> float:
    """Generalised Equivalent Uniform Dose from differential DVH."""
    if dvh_df is None or dvh_df.empty or a == 0:
        return math.nan

    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols = np.asarray(dvh_df["volume_frac"], dtype=float)
    mask = doses > 0
    if not mask.any():
        return math.nan

    doses = doses[mask]
    vols = vols[mask]
    vols = vols / vols.sum()

    try:
        if a < 0:
            powered = np.power(doses, a)
            if np.any(powered <= 0):
                return math.nan
            geud = float(np.power(np.sum(vols * powered), 1.0 / a))
        else:
            geud = float(np.power(np.sum(vols * np.power(doses, a)), 1.0 / a))
        if np.iscomplexobj(geud) or math.isnan(geud):
            return math.nan
        return geud
    except (ValueError, FloatingPointError, ZeroDivisionError):
        logger.warning("compute_geud failed for a=%s", a)
        return math.nan


def geud_tcp_niemierko(geud_gy: float, TCD50_gy: float, gamma50: float) -> float:
    """Niemierko logistic gEUD-TCP."""
    if geud_gy <= 0 or TCD50_gy <= 0 or gamma50 <= 0:
        return math.nan
    try:
        ratio = TCD50_gy / geud_gy
        tcp = 1.0 / (1.0 + ratio ** (4.0 * gamma50))
        return float(np.clip(tcp, 0.0, 1.0))
    except (OverflowError, ValueError):
        return math.nan


class GEUDTCPCalculator:
    """gEUD-TCP calculator."""

    def compute_tcp(self, dvh_df: pd.DataFrame, site_params: TCPSiteParams) -> dict:
        geud_gy = compute_geud(dvh_df, site_params.geud_a)
        tcp = geud_tcp_niemierko(geud_gy, site_params.TCD50_gy, site_params.gamma50)
        return {
            "tcp": tcp,
            "geud_gy": geud_gy,
            "TCD50_gy": site_params.TCD50_gy,
            "gamma50": site_params.gamma50,
            "a": site_params.geud_a,
            "model": "gEUD-TCP-Niemierko",
        }
