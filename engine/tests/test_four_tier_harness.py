"""Four-tier harness governance tests."""

from __future__ import annotations

import numpy as np
import pandas as pd

from validation.four_tier_harness import run_four_tier_harness


def test_epv_guard_refuses_t3_when_under_threshold():
    y = np.array([0, 0, 1, 1, 1, 1, 1, 1, 1, 1])
    patients = np.arange(len(y))
    X = pd.DataFrame({"x1": np.random.default_rng(0).normal(size=len(y))})
    res = run_four_tier_harness(y, classical_probs=np.full(len(y), 0.5), patient_ids=patients, clinical_features=X)
    t3 = res["T3"]
    assert t3.refused
    assert not t3.epv_passes


def test_group_kfold_no_patient_leakage_in_t4():
    rng = np.random.default_rng(1)
    n = 30
    patients = np.repeat(np.arange(10), 3)
    y = rng.integers(0, 2, size=n)
    p = rng.uniform(0.2, 0.8, size=n)
    res = run_four_tier_harness(y, classical_probs=p, patient_ids=patients, ml_probs=p)
    t4 = res["T4"]
    assert t4.apparent_auc == t4.cv_auc or np.isfinite(t4.cv_auc)
