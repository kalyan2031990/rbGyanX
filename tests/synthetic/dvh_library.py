"""
Canonical DVH fixtures with closed-form metric anchors.

Version: 1.0.0 — regenerate golden values via tests/synthetic/test_regression_anchors.py
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class DVHSpec:
    name: str
    dvh: pd.DataFrame
    d_mean: float
    d_min: float
    d_max: float
    geud_a1: float  # gEUD with a=1 → arithmetic mean dose


def uniform_dvh(dose_gy: float) -> DVHSpec:
    df = pd.DataFrame({"dose_gy": [dose_gy], "volume_frac": [1.0]})
    return DVHSpec(
        name=f"uniform_{dose_gy}Gy",
        dvh=df,
        d_mean=dose_gy,
        d_min=dose_gy,
        d_max=dose_gy,
        geud_a1=dose_gy,
    )


def ramp_dvh(d_min: float, d_max: float, n: int = 200) -> DVHSpec:
    doses = np.linspace(d_min, d_max, n)
    frac = np.full(n, 1.0 / n)
    df = pd.DataFrame({"dose_gy": doses, "volume_frac": frac})
    mean = float((doses * frac).sum())
    return DVHSpec(
        name=f"ramp_{d_min}_{d_max}",
        dvh=df,
        d_mean=mean,
        d_min=d_min,
        d_max=d_max,
        geud_a1=mean,
    )


def empty_dvh() -> DVHSpec:
    return DVHSpec(
        name="empty",
        dvh=pd.DataFrame(columns=["dose_gy", "volume_frac"]),
        d_mean=math.nan,
        d_min=math.nan,
        d_max=math.nan,
        geud_a1=math.nan,
    )


def step_dvh(low: float, high: float, frac_high: float = 0.5) -> DVHSpec:
    frac_low = 1.0 - frac_high
    df = pd.DataFrame(
        {
            "dose_gy": [low, high],
            "volume_frac": [frac_low, frac_high],
        }
    )
    mean = low * frac_low + high * frac_high
    return DVHSpec(
        name=f"step_{low}_{high}",
        dvh=df,
        d_mean=mean,
        d_min=low,
        d_max=high,
        geud_a1=mean,
    )


CANONICAL_DVHS: list[DVHSpec] = [
    uniform_dvh(60.0),
    uniform_dvh(26.0),
    ramp_dvh(10.0, 70.0),
    step_dvh(20.0, 66.0, 0.3),
    empty_dvh(),
]
