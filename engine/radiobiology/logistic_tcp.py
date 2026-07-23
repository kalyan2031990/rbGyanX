"""Webb-Nahum logistic TCP model."""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING

import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from config.site_params import TCPSiteParams

logger = logging.getLogger(__name__)


def logistic_tcp(dmean_gy: float, D50_gy: float, k: float) -> float:
    """Webb-Nahum logistic TCP: TCP = 1 / (1 + (D50/Dmean)^k)."""
    if dmean_gy <= 0 or D50_gy <= 0 or k <= 0:
        return math.nan
    try:
        ratio = (D50_gy / dmean_gy) ** k
        if ratio < 0.004:
            return 1.0
        tcp = 1.0 / (1.0 + ratio)
        return float(np.clip(tcp, 0.0, 1.0))
    except (OverflowError, ValueError):
        return math.nan


class LogisticTCPCalculator:
    """Logistic TCP from DVH mean dose."""

    def compute_tcp(self, dvh_df: pd.DataFrame, site_params: TCPSiteParams) -> dict:
        if dvh_df is None or dvh_df.empty:
            dmean = math.nan
        else:
            dmean = float((dvh_df["dose_gy"] * dvh_df["volume_frac"]).sum())
        tcp = logistic_tcp(dmean, site_params.D50_logistic_gy, site_params.k_logistic)
        return {
            "tcp": tcp,
            "Dmean_gy": dmean,
            "D50_gy": site_params.D50_logistic_gy,
            "k": site_params.k_logistic,
            "model": "Logistic-Webb-Nahum",
        }
