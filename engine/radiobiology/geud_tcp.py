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

#: Reason written on a row whose gEUD was driven to zero by an unirradiated sub-volume.
GEUD_ZERO_DOSE_NEG_A = "GEUD_ZERO_DOSE_NEG_A"


def compute_geud_with_reason(dvh_df: pd.DataFrame, a: float) -> tuple[float, str]:
    """gEUD from a differential DVH, with the reason for a degenerate answer.

    Zero-dose bins are part of the structure and are kept (defect #45). For a > 0 they simply
    contribute nothing to the sum. For a < 0 the generalised mean has no finite value when any
    occupied bin sits at 0 Gy: its limit is 0.0, which is returned together with
    ``GEUD_ZERO_DOSE_NEG_A`` so the caller can say why rather than publishing a bare zero.

    Returns the gEUD in Gy (NaN when it cannot be computed) and a reason string, empty when
    the value is an ordinary one.
    """
    if dvh_df is None or dvh_df.empty or a == 0:
        return math.nan, ""

    doses = np.asarray(dvh_df["dose_gy"], dtype=float)
    vols = np.asarray(dvh_df["volume_frac"], dtype=float)
    if doses.size == 0 or doses.size != vols.size:
        return math.nan, ""
    if not np.all(np.isfinite(doses)) or not np.all(np.isfinite(vols)):
        return math.nan, ""
    if np.any(doses < 0):
        return math.nan, ""  # a negative dose is a parsing fault, not a cold spot

    total_vol = float(vols.sum())
    if not math.isfinite(total_vol) or total_vol <= 0:
        return math.nan, ""  # zero-volume / degenerate ROI -> NaN, never 0.0

    occupied = vols > 0
    doses = doses[occupied]
    vols = vols[occupied] / total_vol
    if doses.size == 0:
        return math.nan, ""

    if a < 0 and bool(np.any(doses == 0.0)):
        return 0.0, GEUD_ZERO_DOSE_NEG_A

    try:
        geud = float(np.power(np.sum(vols * np.power(doses, a)), 1.0 / a))
    except (ValueError, FloatingPointError, ZeroDivisionError):
        logger.warning("compute_geud failed for a=%s", a)
        return math.nan, ""
    if not math.isfinite(geud):
        return math.nan, ""
    return geud, ""


def compute_geud(dvh_df: pd.DataFrame, a: float) -> float:
    """Generalised Equivalent Uniform Dose from differential DVH."""
    return compute_geud_with_reason(dvh_df, a)[0]


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
        geud_gy, reason = compute_geud_with_reason(dvh_df, site_params.geud_a)
        tcp = geud_tcp_niemierko(geud_gy, site_params.TCD50_gy, site_params.gamma50)
        return {
            "tcp": tcp,
            "geud_gy": geud_gy,
            "geud_reason": reason,
            "TCD50_gy": site_params.TCD50_gy,
            "gamma50": site_params.gamma50,
            "a": site_params.geud_a,
            "model": "gEUD-TCP-Niemierko",
        }
