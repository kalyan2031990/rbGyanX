import numpy as np
import pytest


def test_safety_guard_fails_on_synthetic():
    from validation.clinical_safety_guard import run_safety_checks

    r = run_safety_checks(
        "XGBoost",
        auc=0.75,
        cv_auc=0.70,
        overfitting_index=0.05,
        calibration_slope=1.0,
        epv=12.0,
        n_patients=40,
        synthetic_data_used=True,
    )
    assert r.overall_status == "FAIL"
    assert "UNRELIABLE" in r.annotation()


def test_safety_guard_passes_good_model():
    from validation.clinical_safety_guard import run_safety_checks

    r = run_safety_checks(
        "XGBoost",
        auc=0.75,
        cv_auc=0.70,
        overfitting_index=0.05,
        calibration_slope=1.0,
        epv=15.0,
        n_patients=50,
    )
    assert r.overall_status == "PASS"
    assert "VALIDATED" in r.annotation()


def test_adaptive_ccs_threshold_scales_with_n():
    from validation.cohort_consistency import _adaptive_ccs_threshold

    assert _adaptive_ccs_threshold(10) < _adaptive_ccs_threshold(50)
    assert _adaptive_ccs_threshold(100) == pytest.approx(_adaptive_ccs_threshold(50))
    assert _adaptive_ccs_threshold(5) >= 0.20


def test_ccs_verdict_key_present():
    from validation.cohort_consistency import compute_ccs

    y = np.array([0, 1] * 6)
    p_cl = np.linspace(0.3, 0.9, 12)
    p_ml = p_cl + np.random.default_rng(0).normal(0, 0.05, 12)
    r = compute_ccs(y, p_cl, p_ml)
    assert r["verdict"] in ("CONSISTENT", "MARGINAL", "INCONSISTENT")
    assert "threshold_used" in r
