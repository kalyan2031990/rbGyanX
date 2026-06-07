"""Relative seriality NTCP from DVH bins."""

from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_ntcp_rs_poisson(
    dvh: pd.DataFrame,
    D50: float,
    gamma: float,
    s: float,
) -> float:
    if D50 <= 0 or gamma <= 0 or s <= 0 or dvh is None or dvh.empty:
        return 0.0
    dose_col = "dose_gy" if "dose_gy" in dvh.columns else "dose"
    vol_col = (
        "volume_cm3"
        if "volume_cm3" in dvh.columns
        else "volume_frac"
        if "volume_frac" in dvh.columns
        else "volume"
    )
    if dose_col not in dvh.columns or vol_col not in dvh.columns:
        return 0.0
    doses = dvh[dose_col].astype(float).values
    vols = dvh[vol_col].astype(float).values
    total_v = vols.sum()
    if total_v <= 0:
        return 0.0
    v_rel = vols / total_v
    try:
        p_voxel = np.power(2.0, -np.exp(gamma * (1.0 - doses / D50)))
        inner = 1.0 - np.power(1.0 - np.power(p_voxel, s), v_rel)
        inner = np.clip(inner, 0.0, 1.0)
        product = np.prod(inner)
        ntcp = np.power(1.0 - product, 1.0 / s)
        return float(np.clip(ntcp, 1e-15, 1.0 - 1e-15))
    except (OverflowError, ZeroDivisionError, ValueError):
        return 0.0
