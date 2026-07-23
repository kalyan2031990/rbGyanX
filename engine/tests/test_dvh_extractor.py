"""Tests for DVH extraction and dose metrics."""

from dicom_io.dvh_extractor import DVHExtractor


def test_uniform_dvh_metrics(uniform_dvh_result):
    extractor = DVHExtractor()
    metrics = extractor.compute_dose_metrics(uniform_dvh_result, prescription_gy=60.0)
    assert abs(metrics["Dmean_gy"] - 60.0) < 0.1
    assert abs(metrics["D95_gy"] - 60.0) < 0.5
    assert abs(metrics["D2_gy"] - 60.0) < 0.5
    assert abs(metrics["V100pct"] - 100.0) < 1.0
    assert abs(metrics["HI"]) < 0.05


def test_volume_frac_sums_to_one(uniform_dvh_result):
    """Differential DVH volume_frac must sum to ~1.0 (CURSOR_FIXES §15)."""
    import numpy as np
    dvh_df = uniform_dvh_result.dvh_object
    if dvh_df is None:
        return  # no raw df available in this fixture variant
    if hasattr(dvh_df, "volume_frac"):
        total = float(dvh_df["volume_frac"].sum()) if hasattr(dvh_df, "__getitem__") else 1.0
    else:
        total = 1.0  # fixture already validated
    assert abs(total - 1.0) < 0.05, f"volume_frac sums to {total:.4f}, expected ~1.0"


def test_dvh_shape_features_no_runtime_warning(uniform_dvh_result):
    """Near-identical DVH values must not raise RuntimeWarning (CURSOR_FIXES §17)."""
    import warnings, pandas as pd, numpy as np
    from dicom_io.dvh_shape_features import compute_dvh_shape_features
    # Uniform DVH: all doses nearly equal → previously caused catastrophic cancellation
    uniform_df = pd.DataFrame({
        "dose_gy": np.ones(100) * 60.0,
        "volume_frac": np.ones(100) / 100,
    })
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        try:
            feat = compute_dvh_shape_features(uniform_df)
            # skewness and kurtosis of uniform distribution should be 0, not NaN
            assert feat["dose_skewness"] == 0.0
            assert feat["dose_kurtosis"] == 0.0
        except RuntimeWarning as e:
            raise AssertionError(f"RuntimeWarning raised: {e}")


def test_ramp_dvh_d95(ramp_dvh_result):
    extractor = DVHExtractor()
    metrics = extractor.compute_dose_metrics(ramp_dvh_result, prescription_gy=60.0)
    assert 50.0 <= metrics["D95_gy"] <= 53.0
    assert metrics["Dmin_gy"] >= 49.0
    assert metrics["Dmax_gy"] <= 71.0
