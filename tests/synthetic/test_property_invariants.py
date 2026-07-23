"""Property-based invariants (dev-only hypothesis)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

hypothesis = pytest.importorskip("hypothesis")
from hypothesis import given, settings
from hypothesis import strategies as st

from radiobiology.geud_tcp import compute_geud
from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson

pytestmark = pytest.mark.unit


@given(
    geud=st.floats(min_value=1.0, max_value=80.0),
    td50=st.floats(min_value=10.0, max_value=80.0),
    gamma=st.floats(min_value=0.5, max_value=6.0),
)
@settings(max_examples=50, deadline=None)
def test_lkb_loglogit_bounded_or_nan(geud, td50, gamma):
    n = calculate_ntcp_lkb_loglogit(geud, td50, gamma)
    assert math.isnan(n) or 0.0 <= n <= 1.0


@given(
    geud=st.floats(min_value=1.0, max_value=80.0),
    td50=st.floats(min_value=10.0, max_value=80.0),
    m=st.floats(min_value=0.05, max_value=1.0),
)
@settings(max_examples=50, deadline=None)
def test_lkb_probit_bounded_or_nan(geud, td50, m):
    n = calculate_ntcp_lkb_probit(geud, td50, m)
    assert math.isnan(n) or 0.0 <= n <= 1.0


@given(dose=st.floats(min_value=55.0, max_value=75.0))
@settings(max_examples=30, deadline=None)
def test_rs_uniform_bounded(dose):
    dvh = pd.DataFrame({"dose_gy": [dose], "volume_frac": [1.0]})
    n = calculate_ntcp_rs_poisson(dvh, D50=50.0, gamma=2.0, s=0.14)
    assert 0.0 <= n <= 1.0


def test_geud_bounded_by_dmin_dmax():
    doses = np.linspace(20.0, 70.0, 100)
    frac = np.ones(100) / 100
    df = pd.DataFrame({"dose_gy": doses, "volume_frac": frac})
    g = compute_geud(df, a=1.0)
    assert 20.0 <= g <= 70.0
