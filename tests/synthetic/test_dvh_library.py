"""Unit tests for canonical synthetic DVH library."""

from __future__ import annotations

import math

import pytest

from tests.synthetic.dvh_library import CANONICAL_DVHS, empty_dvh, uniform_dvh

pytestmark = pytest.mark.unit


def test_uniform_dvh_mean_equals_dose():
    spec = uniform_dvh(60.0)
    assert spec.d_mean == pytest.approx(60.0)
    assert spec.d_min == spec.d_max == 60.0


def test_empty_dvh_metrics_nan():
    spec = empty_dvh()
    assert math.isnan(spec.d_mean)


@pytest.mark.parametrize("spec", CANONICAL_DVHS, ids=lambda s: s.name)
def test_dvh_has_required_columns(spec):
    if spec.name == "empty":
        assert spec.dvh.empty
    else:
        assert "dose_gy" in spec.dvh.columns
        assert "volume_frac" in spec.dvh.columns
        assert abs(spec.dvh["volume_frac"].sum() - 1.0) < 1e-9
