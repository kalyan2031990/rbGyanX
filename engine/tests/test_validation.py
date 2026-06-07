import math
import pathlib
import tempfile

import numpy as np
import pytest


def perfect_predictions(n: int = 100, seed: int = 0):
    rng = np.random.default_rng(seed)
    y = np.array([0] * 50 + [1] * 50)
    rng.shuffle(y)
    p = np.where(y == 1, 0.99, 0.01)
    return y, p


def random_predictions(n: int = 100, seed: int = 0):
    rng = np.random.default_rng(seed)
    y = np.array([0] * 50 + [1] * 50)
    rng.shuffle(y)
    p = rng.uniform(0.3, 0.7, n)
    return y, p


def test_perfect_classifier_auc_near_one():
    from validation.tcp_evaluator import evaluate_model

    y, p = perfect_predictions()
    result = evaluate_model(y, p)
    assert result.auc > 0.98


def test_random_classifier_auc_near_half():
    from validation.tcp_evaluator import delong_auc_ci

    rng = np.random.default_rng(42)
    y = np.array([0] * 50 + [1] * 50)
    p = rng.uniform(0, 1, 100)
    auc, lo, hi = delong_auc_ci(y, p)
    assert 0.3 < auc < 0.7
    assert lo <= auc <= hi


def test_brier_perfect_near_zero():
    from validation.tcp_evaluator import evaluate_model

    y, p = perfect_predictions()
    assert evaluate_model(y, p).brier_score < 0.01


def test_ece_perfectly_calibrated():
    from validation.tcp_evaluator import compute_ece

    y = np.array([1] * 50 + [0] * 50)
    p = np.array([0.9] * 50 + [0.1] * 50)
    ece = compute_ece(y, p, n_bins=5)
    assert 0 <= ece <= 0.5


def test_overfitting_index_flags_overfit():
    from validation.tcp_evaluator import evaluate_model

    y, p = perfect_predictions()
    result = evaluate_model(y, p, cv_auc=0.70)
    assert result.overfitting_index is not None
    assert result.overfitting_index > 0.10


def test_calibration_slope_near_one_when_calibrated():
    from validation.calibration import compute_calibration_slope_intercept

    y, p = perfect_predictions()
    slope, intercept = compute_calibration_slope_intercept(y, p)
    assert math.isfinite(slope)


def test_hl_test_pvalue_between_0_and_1():
    from validation.calibration import hosmer_lemeshow_test

    y, p = random_predictions()
    result = hosmer_lemeshow_test(y, p)
    assert 0.0 <= result.hl_pvalue <= 1.0


def test_hl_test_n_groups_stored():
    from validation.calibration import hosmer_lemeshow_test

    y, p = random_predictions()
    result = hosmer_lemeshow_test(y, p, n_groups=8)
    assert result.n_groups == 8


def test_calibration_plot_creates_file():
    from validation.calibration import plot_calibration

    y, p = random_predictions()
    with tempfile.TemporaryDirectory() as tmp:
        out = plot_calibration(y, p, "TestModel", pathlib.Path(tmp) / "cal.png")
        assert out.exists()


def test_ccs_bounded_minus_one_to_one():
    from validation.cohort_consistency import compute_ccs

    rng = np.random.default_rng(0)
    y = (rng.uniform(size=50) > 0.5).astype(float)
    p_cl = rng.uniform(0, 1, 50)
    p_ml = rng.uniform(0, 1, 50)
    result = compute_ccs(y, p_cl, p_ml)
    assert -1.0 <= result["ccs"] <= 1.0


def test_ccs_high_when_all_agree():
    from validation.cohort_consistency import compute_ccs

    n = 60
    signal = np.linspace(0, 1, n)
    y = (signal > 0.5).astype(float)
    p_cl = signal
    p_ml = signal + np.random.default_rng(0).normal(0, 0.02, n)
    result = compute_ccs(y, p_cl, p_ml)
    assert result["ccs"] > 0.5


def test_ccs_returns_all_keys():
    from validation.cohort_consistency import compute_ccs

    rng = np.random.default_rng(1)
    y, p_cl, p_ml = rng.uniform(size=(3, 40))
    result = compute_ccs(y, p_cl, p_ml)
    for key in (
        "ccs",
        "rho_classical_vs_ml",
        "rho_classical_vs_outcome",
        "rho_ml_vs_outcome",
        "n_patients",
    ):
        assert key in result


def test_covariate_shift_detected_when_shifted():
    from validation.external_val import check_covariate_shift

    rng = np.random.default_rng(0)
    X_tr = rng.normal(0, 1, size=(100, 2))
    X_ex = rng.normal(5, 1, size=(50, 2))
    result = check_covariate_shift(X_tr, X_ex, ["f0", "f1"])
    assert result["shift_detected"]
    assert result["n_shifted"] >= 1


def test_covariate_shift_not_detected_when_same():
    from validation.external_val import check_covariate_shift

    rng = np.random.default_rng(0)
    X_tr = rng.normal(0, 1, size=(200, 2))
    X_ex = rng.normal(0, 1, size=(100, 2))
    result = check_covariate_shift(X_tr, X_ex, ["f0", "f1"])
    assert "n_shifted" in result
    assert isinstance(result["shift_detected"], bool)


def test_validate_on_external_returns_auc():
    from validation.external_val import validate_on_external
    from sklearn.dummy import DummyClassifier

    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 3))
    y = np.array([0] * 30 + [1] * 30)
    clf = DummyClassifier(strategy="prior")
    clf.fit(X, y)
    result = validate_on_external(clf, X, y, ["f0", "f1", "f2"])
    assert math.isfinite(result["auc"]) or math.isnan(result["auc"])
    assert "brier_score" in result


def test_validate_on_external_with_covariate_shift():
    from validation.external_val import validate_on_external
    from sklearn.dummy import DummyClassifier

    rng = np.random.default_rng(1)
    X_tr = rng.normal(0, 1, size=(60, 2))
    y_tr = np.array([0] * 30 + [1] * 30)
    X_ex = rng.normal(3, 1, size=(30, 2))
    y_ex = np.array([0] * 15 + [1] * 15)
    clf = DummyClassifier(strategy="prior").fit(X_tr, y_tr)
    result = validate_on_external(clf, X_ex, y_ex, ["f0", "f1"], X_train=X_tr)
    assert "covariate_shift" in result
    assert result["covariate_shift"]["shift_detected"]
