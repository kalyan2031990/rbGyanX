"""Relative seriality NTCP from DVH bins (Källman / Ågren formalism).

Voxel control probability (implemented form):
    P(D) = 2^(-exp(gamma_eff * (1 - D/D50)))

Parameter note (see docs/RS_PARAMETRISATION.md):
    YAML packs store ``gamma`` as ``gamma_eff`` for this implementation.
    Literature γ50 in the canonical form P(D)=2^(-exp(e·γ50·(1-D/D50))) relates as
    gamma_eff = e * γ50.  The fixed point P(D50)=0.5 holds for both conventions.

References:
    Källman P, Lind BK, Brahme A. Phys Med Biol 1992;37:871-890.
    Ågren A-K, Brahme A, Turesson I. Int J Radiat Oncol Biol Phys 1990;19:1077-1085.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

_NTCP_CLIP_LO = 1e-15
_NTCP_CLIP_HI = 1.0 - 1e-15
_EXP_ARG_CLIP = 700.0  # avoid overflow in exp()


def _nan() -> float:
    return float("nan")


def calculate_ntcp_rs_poisson(
    dvh: pd.DataFrame,
    D50: float,
    gamma: float,
    s: float,
) -> float:
    """Relative-seriality NTCP from a differential DVH."""
    if (
        math.isnan(D50)
        or D50 <= 0
        or math.isnan(gamma)
        or gamma <= 0
        or math.isnan(s)
        or s <= 0
        or dvh is None
        or dvh.empty
    ):
        return _nan()

    dose_col = "dose_gy" if "dose_gy" in dvh.columns else "dose"
    vol_col = (
        "volume_cm3"
        if "volume_cm3" in dvh.columns
        else "volume_frac"
        if "volume_frac" in dvh.columns
        else "volume"
    )
    if dose_col not in dvh.columns or vol_col not in dvh.columns:
        return _nan()

    doses = dvh[dose_col].astype(float).values
    vols = dvh[vol_col].astype(float).values
    total_v = vols.sum()
    if total_v <= 0:
        return _nan()

    v_rel = vols / total_v
    try:
        arg = np.clip(gamma * (1.0 - doses / D50), -_EXP_ARG_CLIP, _EXP_ARG_CLIP)
        p_voxel = np.power(2.0, -np.exp(arg))
        inner = 1.0 - np.power(1.0 - np.power(p_voxel, s), v_rel)
        inner = np.clip(inner, 0.0, 1.0)
        product = np.prod(inner)
        ntcp = np.power(1.0 - product, 1.0 / s)
        return float(np.clip(ntcp, _NTCP_CLIP_LO, _NTCP_CLIP_HI))
    except (OverflowError, ZeroDivisionError, ValueError):
        return _nan()
