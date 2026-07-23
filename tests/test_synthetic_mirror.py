"""Synthetic-mirror generator must yield a benchmark-ready, schema-complete table."""

from __future__ import annotations

import pandas as pd
from external_validation.make_synthetic_mirror import make_synthetic_cohort

from validation.extval_benchmark import feature_matrix, run_benchmark


def test_mirror_schema_and_endpoints():
    df = make_synthetic_cohort(n=100, seed=0)
    assert len(df) == 100
    for col in ("patient_id", "centre", "locoregional", "death", "PTV_EQD2_gy", "age"):
        assert col in df.columns
    # binary, non-degenerate endpoints
    assert set(df["locoregional"].unique()) <= {0, 1}
    assert 0 < df["locoregional"].sum() < len(df)
    # dysphagia-OAR columns present for the benchmark feature set
    x, names = feature_matrix(df, "dosiomics")
    assert any(n.startswith("Parotids_") for n in names)
    assert "PTV_dose_skewness" in names


def test_mirror_runs_through_benchmark():
    df = make_synthetic_cohort(n=100, seed=1)
    table, extras = run_benchmark(
        df, endpoint="locoregional", feature_set="dosiomics", lambda_phys_sweep=(), n_splits=3
    )
    assert extras["n"] == 100
    assert {"C1.T1", "C1.T2", "C3.T4"}.issubset(set(table["tier"]))
    assert isinstance(table, pd.DataFrame) and not table.empty
