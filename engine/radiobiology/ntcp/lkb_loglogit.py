"""LKB NTCP with log-logistic link."""

from __future__ import annotations

import numpy as np


def calculate_ntcp_lkb_loglogit(geud: float, TD50: float, gamma50: float) -> float:
    if np.isnan(geud) or geud <= 0 or TD50 <= 0 or gamma50 <= 0:
        return 0.0
    try:
        ratio = TD50 / geud
        ntcp = 1.0 / (1.0 + np.power(ratio, 4.0 * gamma50))
        return float(np.clip(ntcp, 1e-15, 1.0 - 1e-15))
    except (OverflowError, ZeroDivisionError):
        return 0.0 if geud < TD50 else 1.0
