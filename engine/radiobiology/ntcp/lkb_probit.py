"""LKB NTCP probit model using gEUD formalism.

Reference: Lyman JT. Int J Radiat Oncol Biol Phys 1985;11(S1):104-109.
           Equation: NTCP = Phi((gEUD - TD50) / (m * TD50)).
"""

from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

_NTCP_CLIP_LO = 1e-15
_NTCP_CLIP_HI = 1.0 - 1e-15


def calculate_ntcp_lkb_probit(
    geud_gy: float,
    TD50_gy: float,
    m: float,
) -> float:
    """LKB NTCP using probit link: NTCP = Phi((gEUD-TD50)/(m*TD50))."""
    if (
        math.isnan(geud_gy)
        or geud_gy <= 0
        or math.isnan(TD50_gy)
        or TD50_gy <= 0
        or math.isnan(m)
        or m <= 0
    ):
        return float("nan")
    try:
        t = (geud_gy - TD50_gy) / (m * TD50_gy)
        return float(np.clip(norm.cdf(t), _NTCP_CLIP_LO, _NTCP_CLIP_HI))
    except (OverflowError, ZeroDivisionError, ValueError):
        return float("nan")
