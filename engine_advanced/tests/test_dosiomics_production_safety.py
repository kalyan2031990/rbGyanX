"""Regression tests for B2: synthetic dose must never enter a production dosiomics pathway.

Two halves, both required:
  1. missing real dose  -> NOT_AVAILABLE, no features, no fabricated voxels;
  2. explicit test mode -> the pipeline is still fully exercisable on synthetic fixtures.
"""

from __future__ import annotations

import numpy as np
import pytest

from rbgyanx_advanced.dose3d.dose_grid_extractor import (
    SOURCE_NOT_AVAILABLE,
    SOURCE_REAL_RTDOSE,
    SOURCE_SYNTHETIC_TEST,
    SyntheticDoseInProductionError,
    assert_production_dose_source,
    extract_oar_dose_volume,
    extract_oar_dose_volume_with_source,
    synthetic_oar_dose_voxels,
)
from rbgyanx_advanced.dose3d.dosiomics import extract_dosiomics_features
from rbgyanx_advanced.integration import attach_dosiomics_to_ntcp_results


# ------------------------------------------------------------------ 1. no real dose -> no features

def test_missing_real_dose_returns_not_available_not_synthetic():
    voxels, source = extract_oar_dose_volume_with_source(None, None, "Parotid_L")
    assert voxels is None
    assert source == SOURCE_NOT_AVAILABLE


def test_missing_real_dose_ignores_fallback_mean_dose():
    """The old signature fabricated voxels around fallback_mean_dose_gy. It must no longer."""
    voxels, source = extract_oar_dose_volume_with_source(
        None, None, "Parotid_L", fallback_mean_dose_gy=45.0
    )
    assert voxels is None
    assert source == SOURCE_NOT_AVAILABLE


def test_legacy_extractor_signature_returns_none_by_default():
    assert extract_oar_dose_volume(None, None, "Parotid_L") is None
    assert extract_oar_dose_volume(None, None, "Parotid_L", fallback_mean_dose_gy=45.0) is None


def test_production_pathway_emits_no_dosio_features_without_real_dose(tmp_path):
    rows = [
        {"structure": "Parotid_L", "Dmean_gy": 26.0, "NTCP_lkb": 0.31},
        {"structure": "Parotid_R", "Dmean_gy": 24.0, "NTCP_lkb": 0.27},
    ]
    any_real = attach_dosiomics_to_ntcp_results(rows, tmp_path)  # empty dir: no RTDOSE/RTSTRUCT

    assert any_real is False
    for row in rows:
        assert row["dosiomics_status"] == SOURCE_NOT_AVAILABLE
        assert not [k for k in row if str(k).startswith("dosio_")], (
            "a production run without a real dose grid must write no dosio_* feature"
        )


def test_production_guard_rejects_synthetic_source():
    with pytest.raises(SyntheticDoseInProductionError):
        assert_production_dose_source(SOURCE_SYNTHETIC_TEST)
    with pytest.raises(SyntheticDoseInProductionError):
        assert_production_dose_source(SOURCE_NOT_AVAILABLE)
    assert_production_dose_source(SOURCE_REAL_RTDOSE)  # the only permitted source


def test_dosiomics_refuses_synthetic_voxels_in_production_mode():
    voxels = synthetic_oar_dose_voxels(n_voxels=200, mean_dose_gy=45.0, seed=3)
    with pytest.raises(SyntheticDoseInProductionError):
        extract_dosiomics_features(
            voxels, oar_name="Parotid_L", dose_source=SOURCE_SYNTHETIC_TEST, production=True
        )


def test_dosiomics_refuses_unlabelled_source_in_production_mode():
    """An omitted dose_source is treated as NOT_AVAILABLE, never as trusted."""
    voxels = np.linspace(10.0, 50.0, 500, dtype=np.float32)
    with pytest.raises(SyntheticDoseInProductionError):
        extract_dosiomics_features(voxels, oar_name="Parotid_L", production=True)


# ------------------------------------------------------------- 2. explicit test mode still works

def test_explicit_test_mode_yields_synthetic_voxels():
    voxels, source = extract_oar_dose_volume_with_source(
        None, None, "Parotid_L", allow_synthetic=True, fallback_mean_dose_gy=45.0
    )
    assert source == SOURCE_SYNTHETIC_TEST
    assert voxels is not None and len(voxels) > 0
    assert 30.0 < float(np.mean(voxels)) < 60.0


def test_explicit_test_mode_exercises_the_full_feature_pipeline():
    voxels, source = extract_oar_dose_volume_with_source(
        None, None, "Parotid_L", allow_synthetic=True, fallback_mean_dose_gy=30.0
    )
    feats = extract_dosiomics_features(voxels, oar_name="Parotid_L", dose_source=source)
    assert len(feats) >= 15
    assert feats["dosio_Parotid_L_mean"] > 0
    # production=False is the only reason this is allowed to return numbers at all
    assert source == SOURCE_SYNTHETIC_TEST


def test_real_source_passes_production_guard():
    voxels = np.linspace(10.0, 50.0, 500, dtype=np.float32)
    feats = extract_dosiomics_features(
        voxels, oar_name="Parotid_L", dose_source=SOURCE_REAL_RTDOSE, production=True
    )
    assert feats["dosio_Parotid_L_mean"] == pytest.approx(float(np.mean(voxels)), rel=1e-9)
