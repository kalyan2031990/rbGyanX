"""Golden anchors for classical models on canonical DVHs."""

from __future__ import annotations

import math

import pytest

from radiobiology.geud_tcp import compute_geud
from radiobiology.lq_model import bed, eqd2
from tests.synthetic.dvh_library import ramp_dvh, uniform_dvh
from radiobiology.ntcp.lkb_loglogit import calculate_ntcp_lkb_loglogit
from radiobiology.ntcp.lkb_probit import calculate_ntcp_lkb_probit
from radiobiology.ntcp.rs_poisson import calculate_ntcp_rs_poisson
from tests.synthetic.dvh_library import uniform_dvh

pytestmark = pytest.mark.unit


def test_bed_84gy_anchor():
    """Emami / standard LQ: 70 Gy / 2 Gy / αβ=10 → BED 84 Gy."""
    assert bed(70.0, 2.0, 10.0) == pytest.approx(84.0, abs=0.01)


def test_geud_a1_equals_mean_for_uniform():
    spec = uniform_dvh(60.0)
    assert compute_geud(spec.dvh, a=1.0) == pytest.approx(60.0, rel=1e-9)


def test_geud_bounded_ramp():
    spec = ramp_dvh(20.0, 70.0)
    g = compute_geud(spec.dvh, a=1.0)
    assert 20.0 <= g <= 70.0


def test_eqd2_identity_at_2gy():
    for d in [50.0, 60.0, 70.0]:
        assert eqd2(d, 2.0, 10.0) == pytest.approx(d, rel=1e-9)


@pytest.mark.parametrize(
    "fn",
    [calculate_ntcp_lkb_loglogit, calculate_ntcp_lkb_probit],
)
def test_lkb_half_at_td50(fn):
    if fn is calculate_ntcp_lkb_loglogit:
        assert fn(26.0, 26.0, 3.0) == pytest.approx(0.5, abs=1e-9)
    else:
        assert fn(26.0, 26.0, 0.4) == pytest.approx(0.5, abs=1e-9)


def test_rs_half_at_d50_serial_golden():
    dvh = uniform_dvh(50.0).dvh
    assert calculate_ntcp_rs_poisson(dvh, 50.0, 2.0, 1.0) == pytest.approx(0.5, abs=1e-6)


def test_empty_dvh_rs_nan():
    from tests.synthetic.dvh_library import empty_dvh

    assert math.isnan(
        calculate_ntcp_rs_poisson(empty_dvh().dvh, 50.0, 2.0, 0.14)
    )
