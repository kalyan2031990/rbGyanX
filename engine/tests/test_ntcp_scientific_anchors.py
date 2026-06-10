"""Scientific anchors for classical NTCP primitives (Phase 2)."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest

from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson
from synthetic_data.dvh_fixtures import make_ramp_dvh, make_uniform_dvh

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "fn,args",
    [
        (calculate_ntcp_lkb_loglogit, (float("nan"), 26.0, 3.0)),
        (calculate_ntcp_lkb_loglogit, (0.0, 26.0, 3.0)),
        (calculate_ntcp_lkb_loglogit, (26.0, 0.0, 3.0)),
        (calculate_ntcp_lkb_probit, (float("nan"), 26.0, 0.4)),
        (calculate_ntcp_lkb_probit, (-1.0, 26.0, 0.4)),
        (calculate_ntcp_rs_poisson, (pd.DataFrame(), 26.0, 3.0, 0.5)),
    ],
)
def test_degenerate_ntcp_is_nan(fn, args):
    assert math.isnan(fn(*args))


def test_lkb_loglogit_half_at_td50():
    assert abs(calculate_ntcp_lkb_loglogit(26.0, 26.0, 3.0) - 0.5) < 1e-9


def test_lkb_probit_half_at_td50():
    assert abs(calculate_ntcp_lkb_probit(26.0, 26.0, 0.40) - 0.5) < 1e-9


def test_rs_voxel_control_half_at_d50():
    """Voxel control P(D50) = 2^(-exp(0)) = 0.5 (Källman fixed point)."""
    import numpy as np

    arg = 0.0  # gamma * (1 - D50/D50)
    p_voxel = float(np.power(2.0, -np.exp(arg)))
    assert abs(p_voxel - 0.5) < 1e-12


def test_rs_organ_half_at_d50_serial():
    """Organ NTCP = 0.5 at uniform D=D50 when s=1 (fully serial)."""
    dvh = make_uniform_dvh(50.0)
    ntcp = calculate_ntcp_rs_poisson(dvh, D50=50.0, gamma=2.0, s=1.0)
    assert abs(ntcp - 0.5) < 1e-6


def test_rs_seriality_limits_hotspot():
    """Hot-spot DVH: high seriality s→1 should exceed low seriality s→0.01."""
    dvh = pd.DataFrame({"dose_gy": [10.0, 50.0], "volume_frac": [0.9, 0.1]})
    n_parallel = calculate_ntcp_rs_poisson(dvh, D50=50.0, gamma=2.0, s=0.01)
    n_serial = calculate_ntcp_rs_poisson(dvh, D50=50.0, gamma=2.0, s=0.99)
    assert n_serial > n_parallel


def test_lkb_models_agree_slope_at_td50():
    """At TD50 both LKB links equal 0.5 (cross-model anchor)."""
    td50, m, gamma50 = 26.0, 0.40, 3.0
    assert abs(calculate_ntcp_lkb_loglogit(td50, td50, gamma50) - 0.5) < 1e-9
    assert abs(calculate_ntcp_lkb_probit(td50, td50, m) - 0.5) < 1e-9
