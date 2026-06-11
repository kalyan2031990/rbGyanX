"""NaN-safety contract for NTCP primitives (paper §2.B)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson


@pytest.mark.parametrize(
    "func,args",
    [
        (calculate_ntcp_lkb_loglogit, (float("nan"), 30.0, 1.0)),
        (calculate_ntcp_lkb_loglogit, (25.0, 0.0, 1.0)),
        (calculate_ntcp_lkb_loglogit, (25.0, 30.0, 0.0)),
        (calculate_ntcp_lkb_probit, (float("nan"), 30.0, 0.2)),
        (calculate_ntcp_lkb_probit, (25.0, -1.0, 0.2)),
        (calculate_ntcp_rs_poisson, (pd.DataFrame(), 30.0, 1.0, 1.0)),
    ],
)
def test_degenerate_ntcp_returns_nan_not_zero(func, args):
    out = func(*args)
    assert math.isnan(out), f"expected NaN, got {out}"


def test_valid_lkb_loglogit_not_nan():
    v = calculate_ntcp_lkb_loglogit(30.0, 30.0, 1.0)
    assert math.isfinite(v) and 0.0 < v < 1.0


def test_valid_lkb_probit_not_nan():
    v = calculate_ntcp_lkb_probit(30.0, 30.0, 0.2)
    assert math.isfinite(v) and 0.0 < v < 1.0


def test_valid_rs_not_nan():
    dvh = pd.DataFrame({"dose_gy": [20.0, 30.0, 40.0], "volume_cm3": [1.0, 1.0, 1.0]})
    v = calculate_ntcp_rs_poisson(dvh, 30.0, 1.0, 1.0)
    assert math.isfinite(v) and 0.0 <= v <= 1.0


def test_empty_dvh_volume_zero_returns_nan():
    dvh = pd.DataFrame({"dose_gy": [30.0], "volume_cm3": [0.0]})
    v = calculate_ntcp_rs_poisson(dvh, 30.0, 1.0, 1.0)
    assert math.isnan(v)
