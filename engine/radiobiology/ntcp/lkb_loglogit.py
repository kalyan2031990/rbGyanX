"""LKB NTCP with log-logistic link.

Reference: Niemierko A, Goitein M. Int J Radiat Oncol Biol Phys 1993;26(1):110-122.
           NTCP = 1 / (1 + (TD50/gEUD)^(4*gamma50)).
"""

from __future__ import annotations

import math

import numpy as np

_NTCP_CLIP_LO = 1e-15
_NTCP_CLIP_HI = 1.0 - 1e-15


def calculate_ntcp_lkb_loglogit(geud: float, TD50: float, gamma50: float) -> float:
    if (
        math.isnan(geud)
        or geud <= 0
        or math.isnan(TD50)
        or TD50 <= 0
        or math.isnan(gamma50)
        or gamma50 <= 0
    ):
        return float("nan")
    try:
        ratio = TD50 / geud
        ntcp = 1.0 / (1.0 + np.power(ratio, 4.0 * gamma50))
        return float(np.clip(ntcp, _NTCP_CLIP_LO, _NTCP_CLIP_HI))
    except (OverflowError, ZeroDivisionError):
        # Saturated response for extreme but valid dose — not missing data
        return 0.0 if geud < TD50 else 1.0
