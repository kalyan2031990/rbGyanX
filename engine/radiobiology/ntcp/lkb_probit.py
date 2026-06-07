"""LKB NTCP probit model using gEUD formalism."""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm


def calculate_ntcp_lkb_probit(
    geud_gy: float,
    TD50_gy: float,
    m: float,
) -> float:
    """LKB NTCP using probit link: NTCP = Phi((gEUD-TD50)/(m*TD50))."""
    if math.isnan(geud_gy) or geud_gy <= 0 or TD50_gy <= 0 or m <= 0:
        return 0.0
    try:
        t = (geud_gy - TD50_gy) / (m * TD50_gy)
        return float(np.clip(norm.cdf(t), 1e-15, 1.0 - 1e-15))
    except (OverflowError, ZeroDivisionError, ValueError):
        return 0.0
