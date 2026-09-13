"""
Tests for the Phase-3 four-class benchmark and the LQ-constrained outcome PINN.

CI-safe: small synthetic cohort with a dose-driven endpoint; no real data, no torch
dependency for the non-PINN paths.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from validation.extval_benchmark import (
    classical_t1,
    feature_matrix,
    net_benefit,
    run_benchmark,
)


def _synthetic_cohort(n: int = 90, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    eqd2 = rng.normal(70, 4, n)
    geud = eqd2 + rng.normal(0, 1, n)
    # recurrence more likely at lower tumour dose (LQ direction)
    p = 1.0 / (1.0 + np.exp(0.5 * (eqd2 - 70)))
    y = (rng.uniform(size=n) < p * 0.4).astype(int)
    centres = rng.choice(["A", "B", "C"], size=n)
    return pd.DataFrame(
        {
            "patient_id": [f"P{i:03d}" for i in range(n)],
            "centre": centres,
            "PTV_EQD2_gy": eqd2,
            "PTV_gEUD_gy": geud,
            "PTV_BED_gy": eqd2 * 1.2,
            "PTV_Dmean_gy": eqd2 + 1,
            "PTV_HI": rng.uniform(0.02, 0.15, n),
            "Parotids_Dmean_gy": rng.uniform(20, 45, n),
            "Larynx_Dmean_gy": rng.uniform(10, 40, n),
            "PTV_dose_skewness": rng.normal(0, 1, n),
            "PTV_dose_kurtosis": rng.normal(0, 1, n),
            "PTV_dose_std_gy": rng.uniform(1, 4, n),
            "age": rng.uniform(45, 80, n),
            "hpv_status": rng.choice(["positive", "negative", None], size=n),
            "locoregional": y,
        }
    )


def test_net_benefit_analytic():
    # Perfect classifier, single threshold: NB = prevalence (all TP, no FP).
    y = np.array([1, 1, 0, 0])
    p = np.array([0.9, 0.8, 0.1, 0.2])
    nb = net_benefit(y, p, thresholds=np.array([0.5]))
    assert abs(nb - 0.5) < 1e-9  # 2 TP / 4, 0 FP
    # All-NaN predictions -> NaN.
    assert np.isnan(net_benefit(y, np.full(4, np.nan)))


def test_classical_t1_monotone_decreasing_in_dose():
    df = pd.DataFrame({"PTV_EQD2_gy": [50, 60, 70, 80, 90]})
    p = classical_t1(df)
    assert np.all(np.diff(p) < 0)  # higher dose -> lower recurrence
    assert np.all((p > 0) & (p < 1))


def test_feature_matrix_dvh_vs_dosiomics():
    df = _synthetic_cohort(20)
    x_dvh, names_dvh = feature_matrix(df, "dvh")
    x_dos, names_dos = feature_matrix(df, "dosiomics")
    assert "PTV_dose_skewness" not in names_dvh
    assert "PTV_dose_skewness" in names_dos
    assert len(names_dos) > len(names_dvh)


def test_run_benchmark_structure_and_optimism():
    df = _synthetic_cohort(90, seed=1)
    # No PINN sweep -> fast; exercises C1-C3 orchestration + metrics.
    table, extras = run_benchmark(
        df, endpoint="locoregional", feature_set="dosiomics", lambda_phys_sweep=(), n_splits=3
    )
    tiers = set(table["tier"])
    assert {"C1.T1", "C1.T2", "C2.T3", "C3.T4"}.issubset(tiers)
    assert extras["n"] == 90
    for col in ("apparent_auc", "cv_auc", "optimism", "brier", "net_benefit"):
        assert col in table.columns
    # Random forest should overfit (apparent >= CV) on small N.
    rf = table.set_index("tier").loc["C3.T4"]
    assert rf["apparent_auc"] >= rf["cv_auc"] - 1e-6


torch = pytest.importorskip("torch")


def test_pinn_fits_predicts_and_respects_physics():
    from validation.outcome_pinn import OutcomePINN, PINNConfig

    rng = np.random.default_rng(0)
    n = 80
    dose = rng.normal(0, 1, n)
    X = np.column_stack([dose, rng.normal(0, 1, (n, 3))])
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(2 * dose))).astype(int)

    m = OutcomePINN(
        dose_idx=0, config=PINNConfig(lambda_phys=1.0, lambda_bc=0.5, epochs=120, seed=0)
    )
    m.fit(X, y)
    proba = m.predict_proba(X)
    assert proba.shape == (n, 2)
    assert np.all((proba >= 0) & (proba <= 1))

    # Physics prior => recurrence probability monotone non-increasing in the dose driver.
    grid = np.zeros((15, 4))
    grid[:, 0] = np.linspace(-3, 3, 15)
    pr = m.predict_proba(grid)[:, 1]
    assert np.mean(np.diff(pr) > 1e-3) < 0.2  # essentially non-increasing
    assert pr[0] > pr[-1]  # low dose more recurrence than high dose


def test_pinn_ablation_lambda_zero_is_plain_nn():
    from validation.outcome_pinn import OutcomePINN, PINNConfig

    rng = np.random.default_rng(2)
    X = rng.normal(0, 1, (60, 4))
    y = (rng.uniform(size=60) < 0.4).astype(int)
    m = OutcomePINN(
        dose_idx=0, config=PINNConfig(lambda_phys=0.0, lambda_bc=0.0, epochs=60, seed=0)
    )
    m.fit(X, y)
    assert m.predict_proba(X).shape == (60, 2)
