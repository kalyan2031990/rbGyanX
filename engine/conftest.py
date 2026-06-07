# engine/conftest.py — engine-specific fixtures only
# sys.path for the engine root is handled by pytest.ini (pythonpath + importlib mode)

"""Shared pytest fixtures for engine tests."""

import numpy as np
import pytest
from dicompylercore.dvh import DVH

from dicom_io.dvh_extractor import DVHResult


@pytest.fixture
def synthetic_uniform_dvh():
    """DVH where entire volume receives exactly 60.0 Gy."""
    bins = np.linspace(0.0, 70.0, 701)
    edge_doses = bins[1:]
    counts = np.where(edge_doses <= 60.0, 100.0, 0.0)
    return DVH(
        counts=counts,
        bins=bins,
        dvh_type="cumulative",
        dose_units="Gy",
        volume_units="cm3",
    )


@pytest.fixture
def synthetic_ramp_dvh():
    """DVH with linear dose ramp from 50 to 70 Gy across the volume."""
    bins = np.linspace(0.0, 70.0, 701)
    edge_doses = bins[1:]
    counts = np.zeros(700)
    mask = (edge_doses > 50.0) & (edge_doses < 70.0)
    counts[edge_doses <= 50.0] = 100.0
    counts[mask] = 100.0 * (70.0 - edge_doses[mask]) / 20.0
    return DVH(
        counts=counts,
        bins=bins,
        dvh_type="cumulative",
        dose_units="Gy",
        volume_units="cm3",
    )


@pytest.fixture
def uniform_dvh_result(synthetic_uniform_dvh):
    return DVHResult(
        roi_number=1,
        raw_name="PTV",
        canonical_name="PTV",
        category="TARGET",
        total_volume_cc=100.0,
        dmin_gy=60.0,
        dmean_gy=60.0,
        dmax_gy=60.0,
        dvh_object=synthetic_uniform_dvh,
        quality_flag="OK",
    )


@pytest.fixture
def ramp_dvh_result(synthetic_ramp_dvh):
    return DVHResult(
        roi_number=2,
        raw_name="GTV",
        canonical_name="GTV",
        category="TARGET",
        total_volume_cc=100.0,
        dmin_gy=50.0,
        dmean_gy=60.0,
        dmax_gy=70.0,
        dvh_object=synthetic_ramp_dvh,
        quality_flag="OK",
    )
