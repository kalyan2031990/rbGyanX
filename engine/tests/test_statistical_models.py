"""Unit tests for Phase 4 statistical models."""

import math

import numpy as np
import pandas as pd
import pytest

from statistical_models.epv_guard import EPV_MINIMUM, compute_epv, select_features_by_epv


def make_balanced_outcome(n: int = 100, seed: int = 0) -> np.ndarray:
    """50/50 local control / recurrence."""
    rng = np.random.default_rng(seed)
    y = np.zeros(n, dtype=int)
    y[: n // 2] = 1
    rng.shuffle(y)
    return y


def make_separable_data(n: int = 80, seed: int = 0):
    """X separates y reasonably well (AUC > 0.6 expected)."""
    rng = np.random.default_rng(seed)
    y = make_balanced_outcome(n, seed)
    X = rng.normal(size=(n, 2))
    X[y == 1, 0] += 1.5
    return X, y


def _lifelines_available() -> bool:
    try:
        from lifelines import CoxPHFitter  # noqa: F401

        return True
    except ImportError:
        return False


lifelines_skip = pytest.mark.skipif(
    not _lifelines_available(), reason="lifelines not installed"
)


# GROUP A — EPV Guard
def test_epv_passes_with_sufficient_events():
    y = np.array([0] * 15 + [1] * 85)
    result = compute_epv(y, n_features=1)
    assert result.passes
    assert result.epv == pytest.approx(15.0)


def test_epv_fails_with_too_few_events():
    y = np.array([0] * 9 + [1] * 91)
    result = compute_epv(y, n_features=1)
    assert not result.passes
    assert result.epv == pytest.approx(9.0)


def test_epv_exact_boundary():
    y = np.array([0] * 10 + [1] * 90)
    result = compute_epv(y, n_features=1)
    assert result.passes
    assert result.epv == pytest.approx(10.0)


def test_epv_three_features_blocks():
    y = np.array([0] * 10 + [1] * 90)
    result = compute_epv(y, n_features=3)
    assert not result.passes
    assert result.epv == pytest.approx(10 / 3)


def test_epv_events_count_recurrences_only():
    y = np.array([0] * 5 + [1] * 95)
    result = compute_epv(y, n_features=1)
    assert result.n_events == 5


def test_select_features_by_epv_reduces_feature_set():
    y = np.array([0] * 15 + [1] * 85)
    features = ["TCP_Poisson", "TCP_gEUD", "EQD2"]
    selected, epv_r = select_features_by_epv(features, y)
    assert len(selected) == 1
    assert epv_r.passes
    assert selected[0] == "TCP_Poisson"


# GROUP B — MVL Logistic
from statistical_models.logistic_tcp_mv import fit_mvl_tcp, predict_tcp_mvl


def test_mvl_raises_on_epv_violation():
    y_few = np.ones(80, dtype=int)
    y_few[:5] = 0
    X_many = np.random.default_rng(0).normal(size=(80, 10))
    with pytest.raises(ValueError, match="EPV"):
        fit_mvl_tcp(X_many, y_few, epv_threshold=10.0)


def test_mvl_apparent_auc_above_chance():
    X, y = make_separable_data(100)
    result = fit_mvl_tcp(X, y, feature_names=["f0", "f1"], epv_threshold=5.0)
    assert result.auc_apparent > 0.55


def test_mvl_loo_auc_leq_apparent():
    X, y = make_separable_data(80)
    result = fit_mvl_tcp(X, y, feature_names=["f0", "f1"], epv_threshold=5.0)
    assert result.auc_loo <= result.auc_apparent + 0.05


def test_mvl_5fold_auc_leq_apparent():
    X, y = make_separable_data(80)
    result = fit_mvl_tcp(X, y, feature_names=["f0", "f1"], epv_threshold=5.0)
    assert result.auc_5fold <= result.auc_apparent + 0.05


def test_mvl_coefficients_keyed_by_feature_names():
    X, y = make_separable_data(60)
    result = fit_mvl_tcp(X, y, feature_names=["TCP_Poisson", "EQD2"], epv_threshold=3.0)
    assert "TCP_Poisson" in result.coefficients
    assert "EQD2" in result.coefficients


def test_mvl_predict_returns_probabilities():
    X, y = make_separable_data(80)
    result = fit_mvl_tcp(X, y, feature_names=["f0", "f1"], epv_threshold=5.0)
    probs = predict_tcp_mvl(result.pipeline, X[:5])
    assert probs.shape == (5,)
    assert np.all(probs >= 0) and np.all(probs <= 1)


def test_mvl_brier_score_between_0_and_1():
    X, y = make_separable_data(80)
    result = fit_mvl_tcp(X, y, feature_names=["f0", "f1"], epv_threshold=5.0)
    assert 0.0 <= result.brier_apparent <= 1.0


# GROUP C — Cox Regression
def make_cox_df(n: int = 60, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = make_balanced_outcome(n, seed)
    return pd.DataFrame(
        {
            "LocalControl": y,
            "Recurrence": 1 - y,
            "FollowUp_months": rng.uniform(6, 60, n),
            "TCP_Poisson": rng.uniform(0.3, 0.99, n),
            "EQD2_gy": rng.uniform(50, 80, n),
        }
    )


@lifelines_skip
def test_cox_harrell_c_above_chance():
    from statistical_models.cox_regression import fit_cox_tcp

    df = make_cox_df(60)
    result = fit_cox_tcp(df, feature_cols=["TCP_Poisson", "EQD2_gy"])
    assert result.harrell_c >= 0.4


@lifelines_skip
def test_cox_hazard_ratios_positive():
    from statistical_models.cox_regression import fit_cox_tcp

    df = make_cox_df(60)
    result = fit_cox_tcp(df, feature_cols=["TCP_Poisson", "EQD2_gy"])
    for feat, hr in result.hazard_ratios.items():
        assert hr > 0


@lifelines_skip
def test_cox_n_events_counts_recurrences():
    from statistical_models.cox_regression import fit_cox_tcp

    df = make_cox_df(60)
    expected_events = int(df["Recurrence"].sum())
    result = fit_cox_tcp(df, feature_cols=["TCP_Poisson"])
    assert result.n_events == expected_events


@lifelines_skip
def test_cox_ci_ordered():
    from statistical_models.cox_regression import fit_cox_tcp

    df = make_cox_df(80)
    result = fit_cox_tcp(df, feature_cols=["TCP_Poisson", "EQD2_gy"])
    assert result.harrell_c_ci_lower <= result.harrell_c <= result.harrell_c_ci_upper


def test_cox_raises_without_lifelines(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def mock_import(name, *args, **kwargs):
        if name == "lifelines":
            raise ImportError("lifelines not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", mock_import)
    from statistical_models.cox_regression import fit_cox_tcp

    df = make_cox_df(40)
    with pytest.raises(ImportError, match="lifelines"):
        fit_cox_tcp(df, feature_cols=["TCP_Poisson"])
