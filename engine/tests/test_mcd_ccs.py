"""MCD-based cohort consistency score tests."""

from __future__ import annotations

import numpy as np

from validation.cohort_consistency import compute_mcd_ccs, compute_raw_covariance_ccs


def _synthetic_cohort_with_outliers(n: int = 40, n_out: int = 3, seed: int = 0):
    rng = np.random.default_rng(seed)
    base = rng.normal(size=(n, 3))
    outliers = rng.normal(loc=8.0, scale=0.5, size=(n_out, 3))
    X = np.vstack([base, outliers])
    out_idx = list(range(n, n + n_out))
    return X, out_idx


def test_mcd_flags_planted_outliers():
    X, out_idx = _synthetic_cohort_with_outliers()
    mcd = compute_mcd_ccs(X)
    raw = compute_raw_covariance_ccs(X)
    mcd_flags = set(mcd["flagged_indices"])
    raw_flags = set(raw["flagged_indices"])
    assert any(i in mcd_flags for i in out_idx)
    assert len(mcd_flags) >= len(raw_flags) or mcd_flags >= raw_flags


def test_continuous_ccs_in_unit_interval():
    X, _ = _synthetic_cohort_with_outliers()
    mcd = compute_mcd_ccs(X)
    for c in mcd["ccs"]:
        assert 0.0 <= c <= 1.0
